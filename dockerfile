# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (if any are needed by your Python packages)
# For example, if psycopg2 (non-binary) was used, you might need:
# RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*
# However, psycopg2-binary and asyncpg usually don't require this.
# Ensure git is installed for the clone_repo functionality
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
# This should ideally be after pip install to leverage Docker layer caching.
# If config.py is at the root with main.py, it will be copied.
COPY . .

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define the command to run the application
# Use 0.0.0.0 to make it accessible from outside the container
# reload=False for production/stable builds
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]