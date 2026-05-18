FROM python:3.12-slim

# 2. Set working directory
WORKDIR /app

# 3. Install system dependencies (git, curl)
RUN apt-get update && apt-get install -y git curl && apt-get clean

# 4. Copy AWS Lambda Web Adapter
# Multi-arch image (0.9.1) automatically provides arm64 binary on M1 Mac
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter

# 4. Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy Application Code
COPY . .
RUN pip install --no-cache-dir -e .[dev]

# 6. Run uvicorn
CMD ["uvicorn", "mind_kernel_mcp.main:app", "--host", "0.0.0.0", "--port", "8080"]
