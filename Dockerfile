# Use the official Python image as the base image
FROM python:3.9-slim-buster

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Create a directory for templates
RUN mkdir -p templates

# Expose the port that the Flask app will run on
EXPOSE 8080

# Run the Flask application using Gunicorn
CMD exec gunicorn --bind :8080 --workers 1 --threads 8 --timeout 0 app:app