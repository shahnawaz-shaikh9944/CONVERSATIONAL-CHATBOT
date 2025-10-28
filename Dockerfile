# Use official Python image
FROM python:3.11.9
expose 8501
# Set working directory
cmd mkdir -p /app
WORKDIR /app
run apt-get update
run apt install -y libgl1-mesa-glx
copy requirements.txt ./requirements.txt
run pip3 install -r requirements.txt
copy . .
ENTRYPOINT ["streamlit", "run"]
CMD ["app/app.py"]




# # Copy files
# COPY . .

# # Install system dependencies
# RUN apt-get update && apt-get install -y \
#     build-essential \
#     libgl1-mesa-glx \
#     && rm -rf /var/lib/apt/lists/*

# # Install Python dependencies
# RUN pip install --upgrade pip
# RUN pip install -r requirements.txt

# # Expose Streamlit default port
# EXPOSE 8501

# # Set environment variables
# ENV PYTHONUNBUFFERED=1

# # Run Streamlit app
# CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]