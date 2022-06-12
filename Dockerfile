FROM python:3.10-bullseye

RUN pip install poetry
COPY pyproject.toml poetry.lock /app/
WORKDIR /app
RUN poetry install

COPY . .

ENTRYPOINT ["poetry", "run", "python"]
CMD ["main.py"]
