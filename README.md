# Система мониторинга и визуализации метрик на базе Prometheus и Grafana

Полнофункциональная система для мониторинга микросервисной архитектуры с собственными метриками, логами, алертами и проверками доступности.

## Архитектура

```
┌─────────────────────────────────────────────────────────┐
│                    Мониторируемые сервисы               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Приложение  │  │   Docker     │  │  Хост (ОС)   │  │
│  │   + metrics  │  │  контейнеры  │  │              │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
└─────────┼──────────────────┼──────────────────┼──────────┘
          │                  │                  │
          └──────┬───────────┴───────────┬──────┘
                 │                       │
         ┌───────▼──────────┐    ┌──────▼────────┐
         │  node-exporter   │    │ blackbox-expr │
         │  (метрики ОС)    │    │ (доступность) │
         └───────┬──────────┘    └──────┬────────┘
                 │                      │
                 └──────────┬───────────┘
                            │
                    ┌───────▼──────────┐
                    │   Prometheus     │
                    │  (сбор метрик)   │
                    └───────┬──────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
        ┌─────▼──────┐ ┌────▼────┐ ┌─────▼──────┐
        │   Grafana  │ │ AlertMgr │ │  Loki      │
        │(графики)   │ │(алерты)  │ │ (логи)     │
        └────────────┘ └──────────┘ └────────────┘
```

## Компоненты

| Компонент | Порт | Назначение |
|-----------|------|-----------|
| **Prometheus** | 9090 | Сбор и хранение метрик |
| **Grafana** | 3000 | Визуализация, dashboards |
| **AlertManager** | 9093 | Маршрутизация алертов (email) |
| **node-exporter** | 9100 | Метрики хоста (CPU, memory, disk) |
| **blackbox-exporter** | 9115 | Проверки доступности (HTTP, TCP) |
| **Loki** | 3100 | Хранилище логов |
| **Promtail** | - | Отправка логов в Loki |

## Быстрый старт

### Требования
- Docker >= 20.10
- Docker Compose >= 1.29
- ~2 ГБ RAM, 5 ГБ диск

### Шаг 1: Подготовка

```bash
cd PracticWork

# Если эти файлы еще не созданы, создай их:
# 1. Пароль для Grafana
cp grafana/config.monitoring.example grafana/config.monitoring
# Отредактируй GF_SECURITY_ADMIN_PASSWORD

# 2. Gmail SMTP пароль (для алертов)
mkdir -p alertmanager/secrets
echo "YOUR_GMAIL_APP_PASSWORD" > alertmanager/secrets/smtp_password
chmod 600 alertmanager/secrets/smtp_password
```

### Шаг 2: Запуск

```bash
docker compose up -d
docker compose ps
```

Ожидаемый результат:
```
NAME                 STATUS              PORTS
prometheus           Up (healthy)        0.0.0.0:9090->9090/tcp
grafana              Up (healthy)        0.0.0.0:3000->3000/tcp
alertmanager         Up (healthy)        0.0.0.0:9093->9093/tcp
node-exporter        Up                  0.0.0.0:9100->9100/tcp
blackbox_exporter    Up                  0.0.0.0:9115->9115/tcp
loki                 Up                  0.0.0.0:3100->3100/tcp
promtail             Up                  -
```

### Шаг 3: Проверка

Откройте в браузере:

- **Prometheus**: http://localhost:9090 → **Status** → **Targets** → все должны быть UP
- **Grafana**: http://localhost:3000 (admin / пароль из config.monitoring)
- **Loki logs**: Grafana → **Explore** → выберите Loki → введите `{job="docker"}`
- **Blackbox проверки**: Prometheus → введите `probe_success`

## Конфигурация

### Prometheus (`prometheus/prometheus.yml`)

```yaml
global:
  scrape_interval: 15s        # Как часто опрашивать targets
  evaluation_interval: 15s    # Как часто проверять alert rules
```

Добавлены targets:
- `prometheus` — сам Prometheus
- `node-exporter` — метрики ОС
- `alertmanager` — статус AlertManager
- `loki` — статус Loki
- `blackbox` — 6 проверок доступности (все сервисы)

### Alerting (`prometheus/alert.rules`)

Определены алерты:
- **ServiceDown** — сервис недоступен > 2 минут (severity: critical)
- **HighLoad** — высокая нагрузка > 0.5 (severity: warning)
- **HighCPUUsage** — CPU > 80% (severity: warning)
- **HighMemoryUsage** — Memory > 85% (severity: warning)
- **DiskSpaceLow** — диск < 15% свободно (severity: warning)

### AlertManager (`alertmanager/alertmanager.yml`)

```yaml
receivers:
  - name: 'email'
    email_configs:
      - to: 'grreenbblue@gmail.com'
        from: 'heathgo.health.app@gmail.com'
        smarthost: 'smtp.gmail.com:587'
        auth_username: 'heathgo.health.app@gmail.com'
        auth_password_file: /run/secrets/smtp_password
        auth_identity: 'heathgo.health.app@gmail.com'
        require_tls: true
```

Все алерты отправляются на email.

### Loki (`loki/loki-config.yml`)

- Хранилище: `/loki` (том)
- Retention: неограниченный
- Promtail автоматически собирает логи из контейнеров

## Использование

### Просмотр метрик в Prometheus

1. http://localhost:9090
2. **Graph** → введите PromQL запрос:
   ```promql
   # Все метрики
   up

   # CPU использование
   100 - (avg(irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

   # Memory свободная
   (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100

   # Доступность всех сервисов
   probe_success{job="blackbox"}
   ```

### Просмотр логов в Loki

1. Grafana → **Explore**
2. Выберите Loki datasource
3. Введите query:
   ```
   {job="docker"}                           # все логи
   {container_name="prometheus"}            # логи Prometheus
   {container_name="grafana"} | json        # логи Grafana в JSON
   ```

### Создание dashboard в Grafana

1. **Create** → **Dashboard**
2. **Add panel** → **Graph**
3. В query выберите Prometheus
4. Введите PromQL:
   ```promql
   node_cpu_seconds_total{mode="idle"}
   ```
5. **Apply** → **Save**

## Backup и восстановление

### Бэкап данных

```bash
./backup.sh
```

Это создаст архив всех томов в папку `backups/`:
- Prometheus данные
- Grafana dashboards и datasources
- Loki логи

### Восстановление

```bash
./backup.sh restore <path-to-backup-tar-gz>
```

## Безопасность

✅ **Уже реализовано:**
- Пароли в отдельных файлах, не в коде
- SMTP пароль читается из файла (не plaintext)
- `.gitignore` исключает все секреты
- TLS для SMTP (require_tls: true)

⚠️ **Нужно для production:**
- HTTPS для Grafana (reverse proxy + TLS)
- Аутентификация (OAuth, SAML)
- Firewall (открыть только необходимые порты)
- Network policies (если Docker Swarm / Kubernetes)

## Troubleshooting

### Targets DOWN в Prometheus
```bash
docker compose logs prometheus | grep error
docker compose exec prometheus curl -s http://node-exporter:9100/metrics | head -5
```

### Prometheus/Grafana не отвечает
```bash
docker compose restart prometheus grafana
```

### AlertManager не отправляет письма
```bash
docker compose logs alertmanager | tail -20
# Проверить конфиг:
docker exec alertmanager amtool config routes
```

### Loki не собирает логи
```bash
docker compose logs promtail
docker exec loki curl -s http://localhost:3100/loki/api/v1/labels
```

## Дальнейшее развитие

### Этап 1: Инструментирование приложений
Добавьте Prometheus client library в ваши сервисы (Python, Node.js, Go и т.д.).
Пример см. в разделе "Инструментирование приложений" ниже.

### Этап 2: Долгое хранение
Добавьте Thanos или Cortex для хранения метрик > 15 дней:
```yaml
remote_write:
  - url: http://thanos-receive:19291/api/v1/receive
```

### Этап 3: Tracing
Добавьте распределённую трассировку (Jaeger / Tempo).

### Этап 4: Kubernetes
Для Kubernetes используйте `kube-prometheus-stack`:
```bash
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack
```

## Инструментирование приложений

### Python (Flask)

```python
from flask import Flask
from prometheus_client import Counter, Histogram, generate_latest
import time

app = Flask(__name__)

# Метрики
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

@app.before_request
def before_request():
    request.start_time = time.time()

@app.after_request
def after_request(response):
    duration = time.time() - request.start_time
    http_requests_total.labels(
        method=request.method,
        endpoint=request.endpoint or 'unknown',
        status=response.status_code
    ).inc()
    request_duration_seconds.labels(
        method=request.method,
        endpoint=request.endpoint or 'unknown'
    ).observe(duration)
    return response

@app.route('/metrics')
def metrics():
    return generate_latest()

@app.route('/api/hello')
def hello():
    return {'message': 'Hello World'}

if __name__ == '__main__':
    app.run(port=5000)
```

### Node.js (Express)

```javascript
const express = require('express');
const client = require('prom-client');

const app = express();

const register = new client.Registry();

const httpRequestDuration = new client.Histogram({
  name: 'http_request_duration_seconds',
  help: 'Duration of HTTP requests in seconds',
  labelNames: ['method', 'route', 'status_code'],
  registers: [register]
});

const httpRequestsTotal = new client.Counter({
  name: 'http_requests_total',
  help: 'Total number of HTTP requests',
  labelNames: ['method', 'route', 'status_code'],
  registers: [register]
});

app.use((req, res, next) => {
  const start = Date.now();
  res.on('finish', () => {
    const duration = (Date.now() - start) / 1000;
    httpRequestDuration
      .labels(req.method, req.route?.path || 'unknown', res.statusCode)
      .observe(duration);
    httpRequestsTotal
      .labels(req.method, req.route?.path || 'unknown', res.statusCode)
      .inc();
  });
  next();
});

app.get('/api/hello', (req, res) => {
  res.json({ message: 'Hello World' });
});

app.get('/metrics', (req, res) => {
  res.set('Content-Type', register.contentType);
  res.end(register.metrics());
});

app.listen(5000);
```

### Go

```go
package main

import (
    "fmt"
    "net/http"
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
    httpRequestsTotal = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "http_requests_total",
            Help: "Total HTTP requests",
        },
        []string{"method", "endpoint", "status"},
    )
    httpRequestDuration = prometheus.NewHistogramVec(
        prometheus.HistogramOpts{
            Name: "http_request_duration_seconds",
            Help: "HTTP request duration",
        },
        []string{"method", "endpoint"},
    )
)

func init() {
    prometheus.MustRegister(httpRequestsTotal)
    prometheus.MustRegister(httpRequestDuration)
}

func helloHandler(w http.ResponseWriter, r *http.Request) {
    timer := prometheus.NewTimer(httpRequestDuration.WithLabelValues(
        r.Method, r.URL.Path,
    ))
    defer timer.ObserveDuration()

    httpRequestsTotal.WithLabelValues(
        r.Method, r.URL.Path, "200",
    ).Inc()

    w.Header().Set("Content-Type", "application/json")
    fmt.Fprintf(w, `{"message":"Hello World"}`)
}

func main() {
    http.HandleFunc("/api/hello", helloHandler)
    http.Handle("/metrics", promhttp.Handler())
    http.ListenAndServe(":5000", nil)
}
```

## Добавление инструментированного приложения в стек

1. Добавьте сервис в `docker-compose.yml`:
   ```yaml
   myapp:
     build: ./myapp
     ports:
       - "5000:5000"
     networks:
       - back
   ```

2. Добавьте job в `prometheus/prometheus.yml`:
   ```yaml
   - job_name: 'myapp'
     static_configs:
       - targets: ['myapp:5000']
   ```

3. Перезагрузите Prometheus:
   ```bash
   docker compose up -d
   docker exec prometheus kill -HUP 1
   ```

4. В Prometheus проверьте метрики:
   ```promql
   http_requests_total{job="myapp"}
   http_request_duration_seconds{job="myapp"}
   ```


