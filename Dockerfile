FROM public.ecr.aws/lambda/python:3.12

# Install git and curl
RUN dnf install -y git && dnf clean all

# Copy project files
COPY pyproject.toml README.md ${LAMBDA_TASK_ROOT}/
COPY mind_kernel_mcp ${LAMBDA_TASK_ROOT}/mind_kernel_mcp
COPY scripts ${LAMBDA_TASK_ROOT}/scripts

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .[dev]

# Default command (optional, can be overridden)
CMD [ "mind_kernel_mcp.lambda_handler.lambda_handler" ]
