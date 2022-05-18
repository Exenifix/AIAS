FROM python:3.10-bullseye

ENV VIRTUAL_ENV=/app/venv
RUN pip3 install -U pip virtualenv
RUN python -m virtualenv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

ENTRYPOINT ["python"]
CMD ["main.py"]
