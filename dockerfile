# Use Python as base image
FROM python:3.11.4

# Set working directory
WORKDIR /app

# Install uv and git (required for pip install -e)
RUN apt-get update && \
    apt-get install -y git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /app/

# Change to the mcp-client directory
WORKDIR /app/mcp-client

# Create and activate virtual environment using uv
RUN pip install -r requirements.txt

# Expose the port Streamlit runs on
EXPOSE 8501

# Set environment variable to make Streamlit accessible on network
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Command to run the application
CMD ["streamlit", "run", "client.py"]