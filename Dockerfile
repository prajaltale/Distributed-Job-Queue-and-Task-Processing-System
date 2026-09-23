# start from a small, official Python image
FROM python:3.12-slim

# set the working directory inside the container — everything happens relative to this
WORKDIR /app

# copy just the requirements file first (before the rest of the code)
# this lets Docker reuse this layer on future builds if requirements.txt hasn't changed, saving time
COPY requirements.txt .

# install every dependency exactly as listed
RUN pip install --no-cache-dir -r requirements.txt

# now copy the rest of your actual project code into the container
COPY . .

# tell Docker this container listens on port 8000 (informational — doesn't actually publish it, that's done in docker-compose.yml)
EXPOSE 8000