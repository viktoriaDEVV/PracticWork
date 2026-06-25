import os
import time
import random
import psutil

from flask import Flask, request, jsonify
from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY

app = Flask(__name__)

process_memory_rss = Gauge('process_memory_rss_bytes', 'Process RSS memory in bytes')
process_memory_vms = Gauge('process_memory_vms_bytes', 'Process VMS memory in bytes')
process_cpu_percent = Gauge('process_cpu_percent', 'Process CPU usage percentage')

http_requests_total = Counter(
    'http_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0)
)

active_requests = Gauge(
    'active_requests',
    'Number of active requests currently being processed'
)

requests_payload_bytes = Histogram(
    'requests_payload_bytes',
    'Size of incoming request payloads in bytes',
    ['method', 'endpoint'],
    buckets=(64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536)
)

business_operations_total = Counter(
    'business_operations_total',
    'Total number of business operations performed',
    ['operation', 'status']
)

db_query_duration_seconds = Histogram(
    'db_query_duration_seconds',
    'Simulated database query duration in seconds',
    ['query_type'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
)

def collect_process_metrics():
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    return {
        'memory_rss_bytes': memory_info.rss,
        'memory_vms_bytes': memory_info.vms,
        'cpu_percent': process.cpu_percent(interval=0),
        'num_fds': process.num_fds() if hasattr(process, 'num_fds') else 0,
    }

@app.before_request
def before_request():
    request.start_time = time.time()
    active_requests.inc()

@app.after_request
def after_request(response):
    duration = time.time() - request.start_time
    endpoint = request.endpoint or 'unknown'

    http_requests_total.labels(
        method=request.method,
        endpoint=endpoint,
        status=response.status_code
    ).inc()

    http_request_duration_seconds.labels(
        method=request.method,
        endpoint=endpoint
    ).observe(duration)

    content_length = request.content_length or 0
    requests_payload_bytes.labels(
        method=request.method,
        endpoint=endpoint
    ).observe(content_length)

    active_requests.dec()
    return response

@app.errorhandler(Exception)
def handle_exception(e):
    active_requests.dec()
    return jsonify({'error': str(e)}), 500

@app.route('/metrics')
def metrics():
    process_metrics = collect_process_metrics()
    process_memory_rss.set(process_metrics['memory_rss_bytes'])
    process_memory_vms.set(process_metrics['memory_vms_bytes'])
    process_cpu_percent.set(process_metrics['cpu_percent'])
    return generate_latest(REGISTRY)

@app.route('/api/hello')
def hello():
    business_operations_total.labels(operation='greeting', status='success').inc()
    return jsonify({'message': 'Hello World', 'service': 'instrumented-app'})

@app.route('/api/users')
def get_users():
    business_operations_total.labels(operation='get_users', status='success').inc()
    users = [
        {'id': 1, 'name': 'Alice', 'email': 'alice@example.com'},
        {'id': 2, 'name': 'Bob', 'email': 'bob@example.com'},
        {'id': 3, 'name': 'Charlie', 'email': 'charlie@example.com'},
    ]
    return jsonify(users)

@app.route('/api/items')
def get_items():
    delay = random.uniform(0.01, 0.1)
    time.sleep(delay)

    db_query_duration_seconds.labels(query_type='select_items').observe(delay)

    business_operations_total.labels(operation='get_items', status='success').inc()
    items = [
        {'id': 1, 'name': 'Item A', 'price': 100},
        {'id': 2, 'name': 'Item B', 'price': 250},
        {'id': 3, 'name': 'Item C', 'price': 500},
    ]
    return jsonify(items)

@app.route('/api/items', methods=['POST'])
def create_item():
    data = request.get_json(silent=True) or {}
    business_operations_total.labels(operation='create_item', status='success').inc()
    return jsonify({'id': 4, 'name': data.get('name', 'New Item'), 'price': data.get('price', 0)}), 201

@app.route('/api/error')
def trigger_error():
    business_operations_total.labels(operation='trigger_error', status='error').inc()
    return jsonify({'error': 'Internal Server Error'}), 500

@app.route('/')
def index():
    return jsonify({'service': 'instrumented-app', 'status': 'running'})

@app.route('/api/health')
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
