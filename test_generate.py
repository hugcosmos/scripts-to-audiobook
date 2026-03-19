import json
import requests
import time

# Test data
payload = {
    "lines": [
        {
            "line_index": 0,
            "character": "Test Character",
            "text": "Hello, this is a test."
        }
    ],
    "character_voices": [
        {
            "character_name": "Test Character",
            "voice_id": "en-US-GuyNeural"
        }
    ],
    "project_id": "test_project_123",
    "title": "Test Audiobook"
}

# Send request to generate audiobook
response = requests.post("http://localhost:8000/api/generate", json=payload)
print("Generate response:", response.json())

# Get job ID
job_id = response.json().get("job_id")
if not job_id:
    print("Failed to get job ID")
    exit(1)

# Check job status
for i in range(10):
    status_response = requests.get(f"http://localhost:8000/api/jobs/{job_id}")
    status_data = status_response.json()
    print(f"Job status: {status_data.get('status')}, progress: {status_data.get('progress')}%")
    
    if status_data.get("status") == "completed":
        print("Job completed successfully!")
        break
    elif status_data.get("status") == "error":
        print("Job failed with error:", status_data.get("error"))
        break
    
    time.sleep(2)

print("Test completed")