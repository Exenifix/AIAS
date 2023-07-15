FROM python:3.11-slim-bookworm

RUN pip install --no-cache-dir 'poetry==1.5.1'
COPY pyproject.toml poetry.lock /app/
WORKDIR /app
RUN poetry install --only main

COPY . .

ENTRYPOINT ["poetry", "run", "python"]
CMD ["main.py"]
