# Use slim Python base image
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy only relevant files
COPY . .

# Install dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Streamlit settings
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_PORT=8005
ENV STREAMLIT_SERVER_ENABLECORS=false

# Port to expose
EXPOSE 8005

# Run the app
CMD ["streamlit", "run", "Home.py"]