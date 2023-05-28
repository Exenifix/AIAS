FROM python:3.11-bullseye

RUN pip install --no-cache-dir 'poetry==1.5.0'
COPY pyproject.toml poetry.lock /app/
WORKDIR /app
RUN poetry install --only main

COPY . .

ENTRYPOINT ["poetry", "run", "python"]
CMD ["main.py"]
