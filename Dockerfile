# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    git \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for Hugging Face Spaces
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Set the working directory to user home
WORKDIR $HOME/app

# Copy the current directory contents into the container at $HOME/app
COPY --chown=user . $HOME/app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir --user -r requirements.txt

# Create the database file and set permissions
RUN touch nexusai_history.db

# Expose the port Streamlit runs on (Hugging Face default)
EXPOSE 7860

# HEALTHCHECK to ensure the app is running
HEALTHCHECK CMD curl --fail http://localhost:7860/_stcore/health

# Run streamlit when the container launches
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0"]