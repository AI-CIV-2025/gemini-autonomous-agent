# Use an official Node.js runtime as a parent image
FROM node:20-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (git for potential future use)
RUN apt-get update && apt-get install -y python3 python3-pip git && rm -rf /var/lib/apt/lists/*

# Copy package.json and package-lock.json (if available)
COPY package*.json ./

# Install Node.js dependencies
RUN npm install

# Install Python dependencies for agents
# Using a requirements.txt is cleaner
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Make the executor script executable
RUN chmod +x ./run_steps.sh

# Expose all necessary ports
EXPOSE 10000 # Main server
EXPOSE 10001 # Reviewer
EXPOSE 10002 # Reflector
EXPOSE 10003 # Strategist
EXPOSE 10004 # Memory
EXPOSE 10005 # Planner

# Define the command to run your app
# We launch all services in the background, and the main web server in the foreground.
CMD ["bash", "-c", "python3 reviewer.py & python3 reflector.py & python3 strategist.py & python3 memory.py & python3 planner.py & node server.js"]
