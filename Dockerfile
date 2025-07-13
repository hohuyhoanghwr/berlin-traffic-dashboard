FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy everything into the container
COPY . .

# Install dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Streamlit server settings
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_PORT=8000
ENV STREAMLIT_SERVER_ENABLECORS=false

# MongoDB environment variables
ENV MONGO_URI=${MONGO_URI}
ENV MONGO_DB_NAME=${MONGO_DB_NAME}
ENV MONGO_COLLECTION_NAME=${MONGO_COLLECTION_NAME}

# Expose the Streamlit port
EXPOSE 8000

# Run Streamlit with correct entry path
CMD ["streamlit", "run", "streamlit_app/Home.py"]
