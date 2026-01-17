FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY json-viewer.html .
COPY tmp_lh_links.json* ./

# Expose the port
EXPOSE 7860

# Set environment variables
ENV PORT=7860
ENV ADMIN_USER=danny

# Run the application
CMD ["python", "app.py"]
