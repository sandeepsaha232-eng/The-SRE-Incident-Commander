FROM python:3.10-slim

# Create a non-root user named user with uid 1000
RUN useradd -m -u 1000 user

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy all python files
COPY --chown=user:user . /app/

# Switch to the non-root user
USER user

# Expose port 7860 for Hugging Face Spaces
EXPOSE 7860

# Command to run the FastAPI app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
