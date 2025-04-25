import streamlit as st
import asyncio
import json
from contextlib import AsyncExitStack
import sys
import os
from dotenv import load_dotenv
import pandas as pd

# Import the necessary components from the provided code
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from openai import OpenAI
import re

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI()

# Connection Manager Class
class ConnectionManager:
    def __init__(self, stdio_server_map, sse_server_map):
        self.stdio_server_map = stdio_server_map
        self.sse_server_map = sse_server_map
        self.sessions = {}
        self.exit_stack = AsyncExitStack()

    async def initialize(self):
        print(self.stdio_server_map)
        # Initialize stdio connections
        for server_name, params in self.stdio_server_map.items():
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(params)
            )
            read, write = stdio_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()
            self.sessions[server_name] = session

        # Initialize SSE connections
        for server_name, url in self.sse_server_map.items():
            sse_transport = await self.exit_stack.enter_async_context(
                sse_client(url=url)
            )
            read, write = sse_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()
            self.sessions[server_name] = session

    async def list_tools(self):
        tool_map = {}
        consolidated_tools = []
        for server_name, session in self.sessions.items():
            tools = await session.list_tools()
            tool_map.update({tool.name: server_name for tool in tools.tools})
            consolidated_tools.extend(tools.tools)
        return tool_map, consolidated_tools

    async def call_tool(self, tool_name, arguments, tool_map):
        server_name = tool_map.get(tool_name)
        if not server_name:
            print(f"Tool '{tool_name}' not found.")
            return

        session = self.sessions.get(server_name)
        if session:
            result = await session.call_tool(tool_name, arguments=arguments)
            return result.content[0].text

    async def close(self):
        await self.exit_stack.aclose()

# Chat function to handle interactions and tool calls
async def chat(
    input_messages,
    tool_map,
    tools=[],
    max_turns=10,
    connection_manager=None,
):
    chat_messages = input_messages[:]
    for _ in range(max_turns):
        result = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=chat_messages,
            tools=tools,
        )

        if result.choices[0].finish_reason == "tool_calls":
            chat_messages.append(result.choices[0].message)

            for tool_call in result.choices[0].message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                # Get server name for the tool just for logging
                server_name = tool_map.get(tool_name, "")

                # Log tool call
                log_message = f"**Tool Call**  \n**Tool Name:** `{tool_name}` from **MCP Server**: `{server_name}`  \n**Input:**  \n```json\n{json.dumps(tool_args, indent=2)}\n```"
                yield {"role": "assistant", "content": log_message}

                # Call the tool and log its observation
                observation = await connection_manager.call_tool(
                    tool_name, tool_args, tool_map
                )
                log_message = f"**Tool Observation**  \n**Tool Name:** `{tool_name}` from **MCP Server**: `{server_name}`  \n**Output:**  \n```json\n{json.dumps(observation, indent=2)}\n```  \n---"
                yield {"role": "assistant", "content": log_message}

                chat_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(observation),
                    }
                )
        else:
            yield {"role": "assistant", "content": result.choices[0].message.content}
            return

    # Generate a final response if max turns are reached
    result = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=chat_messages,
    )
    yield {"role": "assistant", "content": result.choices[0].message.content}

# Filter and validate input schema for tools
def filter_input_schema(input_schema):
    if "properties" in input_schema:
        if "required" not in input_schema or not isinstance(
            input_schema["required"], list
        ):
            input_schema["required"] = list(input_schema["properties"].keys())
        else:
            for key in input_schema["properties"].keys():
                if key not in input_schema["required"]:
                    input_schema["required"].append(key)

        for key, value in input_schema["properties"].items():
            if "default" in value:
                del value["default"]

        if "additionalProperties" not in input_schema:
            input_schema["additionalProperties"] = False

    return input_schema

# Server maps
stdio_server_map = {
    "clinicaltrials-mcp": StdioServerParameters(
        command="python",
        args=["../mcps/clinicaltrialsgov_mcp.py"],
    ),
    "biorxiv-mcp": StdioServerParameters(
        command="python",
        args=["../mcps/bioarxiv_mcp.py"],
    ),
    "opentargets-mcp": StdioServerParameters(
        command="python",
        args=["../mcps/opentargets_mcp.py"],
    ),
}
sse_server_map = {}

async def initialize_servers():
    connection_manager = ConnectionManager(stdio_server_map, sse_server_map)
    await connection_manager.initialize()
    return connection_manager

# Main function from the provided code
async def main(input):
    connection_manager = await initialize_servers()

    tool_map, tool_objects = await connection_manager.list_tools()

    tools_json = [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "strict": True,
                "parameters": filter_input_schema(tool.inputSchema),
            },
        }
        for tool in tool_objects
    ]
    
    input_messages = [
        {
            "role": "system",
            "content": "Your are an expert in the field of medical science. Keep using the tools until you reach the final objective.",
        },
        {"role": "user", "content": input},
    ]

    responses = []


    async for response in chat(
        input_messages,
        tool_map,
        tools=tools_json,
        connection_manager=connection_manager,
    ):
        responses.append(response)

    await connection_manager.close()
    return responses, tools_json, tool_map

# Function to run the async main function
def run_async_main(input_text):
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(main(input_text))
    finally:
        loop.close()

async def get_tools():
    connection_manager = await initialize_servers()
    tool_map, tool_objects = await connection_manager.list_tools()
    tools_json = [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "strict": True,
                "parameters": filter_input_schema(tool.inputSchema),
            },
        }
        for tool in tool_objects
    ]
    await connection_manager.close()
    return tools_json, tool_map

# Streamlit app
def display_response(response):
    if response["role"] == "assistant":
        content = response["content"]
        
        # Check if this is a tool call
        if content.startswith("**Tool Call**"):
            # Extract tool name and server
            tool_match = re.search(r"\*\*Tool Name:\*\* `([^`]+)` from \*\*MCP Server\*\*: `([^`]+)`", content)
            if tool_match:
                tool_name, server_name = tool_match.groups()
                
                # Extract input JSON
                input_match = re.search(r"```json\n(.*?)\n```", content, re.DOTALL)
                if input_match:
                    try:
                        input_json = json.loads(input_match.group(1))
                        
                        # Create a nice UI for tool calls
                        with st.expander(f"🔍 Tool Call: {tool_name}", expanded=True):
                            st.info(f"Using tool from {server_name} server")
                            
                            # Display parameters in a clean table format
                            st.write("Parameters:", input_json)

                    except json.JSONDecodeError:
                        st.markdown(content)
                else:
                    st.markdown(content)
            else:
                st.markdown(content)
                
        # Check if this is a tool observation
        elif content.startswith("**Tool Observation**"):
            # Extract tool name and server
            tool_match = re.search(r"\*\*Tool Name:\*\* `([^`]+)` from \*\*MCP Server\*\*: `([^`]+)`", content)
            if tool_match:
                tool_name, server_name = tool_match.groups()
                
                # Extract output JSON
                output_match = re.search(r"```json\n(.*?)\n```", content, re.DOTALL)
                if output_match:
                    try:
                        output_text = output_match.group(1).strip('"')
                        # Remove escaped newlines and replace with actual newlines
                        output_text = output_text.replace("\\n", "\n")
                        
                        with st.expander(f"📊 Results from {tool_name}", expanded=True):
                            st.text_area("Raw Result:", value=output_text, height=200)
                    except Exception as e:
                        st.markdown(content)
                else:
                    st.markdown(content)
            else:
                st.markdown(content)
        
        # For final summarized results
        else:
            st.markdown("## 📋 Summary Results")
            st.markdown(content)


def display_tools_info(tools_json, tool_map):
    with st.expander("Available Tools Information"):
        st.subheader("Tool Map")
        tool_server_data = [{"Tool Name": tool, "Server": server} for tool, server in tool_map.items()]
        st.dataframe(pd.DataFrame(tool_server_data))
        
        st.subheader("Tool Details")
        for tool in tools_json:
            with st.expander(f"{tool['function']['name']}"):
                st.markdown(f"**Description**: {tool['function']['description']}")
                st.markdown("**Parameters**:")
                st.json(tool['function']['parameters'])

# Streamlit app
st.title("Medical Research Assistant")
st.markdown("This application uses specialized medical research tools to answer your queries.")

# User input
user_query = st.text_area(
    "Enter your medical research question:", 
    height=100,
    placeholder="Example: What are the latest clinical trials for lung cancer?"
)

# Process button
if st.button("Process Query"):
    if user_query:
        with st.spinner("Processing your query with specialized tools..."):
            # try:
                # Run the main function
                responses, tools_json, tool_map = run_async_main(user_query)
                print({"responses":responses})
                print(tools_json)
                print(tool_map)
                # Display the responses
                st.subheader("Results")
                for response in responses:
                    display_response(response)
                
                # Display tools information
                # display_tools_info(tools_json, tool_map)
                
            # except Exception as e:
            #     st.error(f"An error occurred: {str(e)}")
    else:
        st.warning("Please enter a query.")

if st.button("Show Available Tools"):
    with st.spinner("Loading available tools..."):
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        tools_json, tool_map=loop.run_until_complete(get_tools())
        loop.close()
        
        ### make a modal
        st.subheader("Available Tools")
        st.markdown("These are the tools available for your queries.")
        for tool in tools_json:
            with st.expander(f"{tool['function']['name']}"):
                st.markdown(f"**Description**: {tool['function']['description']}")
                st.markdown("**Parameters**:")
                st.json(tool['function']['parameters'])
        # Display the tool map
        st.subheader("Tool Map")
        tool_server_data = [{"Tool Name": tool, "Server": server} for tool, server in tool_map.items()]
        st.dataframe(pd.DataFrame(tool_server_data))
        

with st.sidebar:
    st.header("About")
    st.markdown("""
    This application integrates with specialized medical research tools using the MCP (Machine Capability Protocol) framework.
    
    Available resources:
    - ClinicalTrials.gov database
    - BioRxiv preprints
    - OpenTargets data
    
    Enter your medical research question, and the system will use these tools to provide comprehensive answers.
    """)