# Use the official Python image from the Docker Hub
FROM python:3.12

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt /app/

# Install the package dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install cron
RUN apt-get update && apt-get install -y cron

# Copy the rest of the application code into the container
COPY . /app/

# Copy the cron job file into the container
COPY cron-jobs /etc/cron.d/cron-jobs

# Give execution rights on the cron job
RUN chmod 0644 /etc/cron.d/cron-jobs

# Apply cron job
RUN crontab /etc/cron.d/cron-jobs

# Create a cron log file to be able to run `tail`
RUN touch /var/log/cron.log

# Don't buffer log output to stdout
ENV PYTHONUNBUFFERED 1

# Entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose the port that the Gunicorn server will run on
EXPOSE 8000
