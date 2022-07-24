FROM python:3.10-bullseye

RUN pip install --no-cache-dir poetry
COPY pyproject.toml poetry.lock /app/
WORKDIR /app
RUN poetry install

COPY . .

ENTRYPOINT ["poetry", "run", "python"]
CMD ["main.py"]
