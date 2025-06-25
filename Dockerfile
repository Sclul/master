FROM python:3.13-alpine

RUN apk update && \
    apk add --no-cache \
        gcc \
        g++ \
        gdal \
        gdal-dev \
        geos \
        proj 

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8050

CMD ["python", "app.py"]