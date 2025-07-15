FROM python:3.12-slim

# Set working directory
WORKDIR /app

COPY streamlit_app/requirements.txt requirements.txt

# Install dependencies
RUN pip install -r requirements.txt

# Copy everything into the container
COPY streamlit_app/ /app/

# MongoDB environment variables
ENV MONGO_URI=${MONGO_URI}
ENV MONGO_DB_NAME=${MONGO_DB_NAME}
ENV MONGO_COLLECTION_NAME=${MONGO_COLLECTION_NAME}

# Expose the Streamlit port
EXPOSE 8505

# Run Streamlit with correct entry path
CMD ["streamlit", "run", "Home.py", "--server.address=0.0.0.0", "--server.port=8505","--server.runOnSave=true"]
