# Currency Rate Microservice

REST API микросервис на FastAPI для получения актуальных курсов валют.  
Контейнеризирован с Docker, развёртывается в Kubernetes (minikube), инфраструктура управляется через Terraform.

---

## Структура репозитория

```
currency-microservice/
├── app.py               # FastAPI-приложение
├── requirements.txt     # Python-зависимости
├── Dockerfile           # Сборка Docker-образа
├── deployment.yaml      # Kubernetes Deployment манифест
├── service.yaml         # Kubernetes Service манифест
├── .gitignore
├── README.md
└── terraform/
    └── main.tf          # Terraform: Deployment + Service
```

---

## 1. Запуск приложения локально (без Docker)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Проверка:
```bash
curl "http://localhost:8000/rate?from=USD&to=RUB"
# {"from":"USD","to":"RUB","rate":92.5}

curl "http://localhost:8000/health"
# {"status":"ok"}
```

Swagger UI доступен по адресу: http://localhost:8000/docs

---

## 2. Сборка и запуск Docker-образа

```bash
# Сборка образа
docker build -t currency-service:latest .

# Запуск контейнера
docker run -d -p 8000:8000 --name currency-svc currency-service:latest

# Проверка
curl "http://localhost:8000/rate?from=EUR&to=RUB"
# {"from":"EUR","to":"RUB","rate":100.3}

# Остановка
docker stop currency-svc && docker rm currency-svc
```

---

## 3. Развёртывание в Kubernetes (minikube)

### 3.1 Подготовка кластера

```bash
# Запустить minikube
minikube start

# ВАЖНО: переключиться на Docker daemon внутри minikube
# чтобы образ был доступен без push в registry
eval $(minikube docker-env)

# Пересобрать образ внутри minikube
docker build -t currency-service:latest .
```

### 3.2 Применение манифестов вручную

```bash
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml

# Проверка состояния
kubectl get pods
kubectl get svc
```

### 3.3 Проверка через port-forward

```bash
kubectl port-forward svc/currency-service 8080:80
# В другом терминале:
curl "http://localhost:8080/rate?from=USD&to=RUB"
```

### 3.4 Проверка через NodePort (minikube)

```bash
minikube service currency-service --url
# Получить URL вида http://192.168.49.2:30080
curl "http://192.168.49.2:30080/rate?from=USD&to=RUB"
```

---

## 4. Управление инфраструктурой через Terraform

```bash
cd terraform/

# Инициализация провайдеров
terraform init

# Предпросмотр изменений
terraform plan

# Применить конфигурацию
terraform apply

# Удалить ресурсы
terraform destroy
```

После `terraform apply` проверить:
```bash
kubectl get pods,svc
curl "$(minikube service currency-service --url)/rate?from=USD&to=RUB"
```

### Переменные Terraform

| Переменная    | По умолчанию             | Описание                        |
|---------------|--------------------------|---------------------------------|
| `kube_context`| `minikube`               | Контекст kubectl                |
| `image_name`  | `currency-service:latest`| Имя Docker-образа               |
| `replicas`    | `2`                      | Количество реплик               |
| `node_port`   | `30080`                  | NodePort для внешнего доступа   |

Переопределить переменную:
```bash
terraform apply -var="replicas=3"
```

---

## 5. Использование внешнего API (опционально)

1. Зарегистрироваться на https://www.exchangerate-api.com/ и получить API-ключ.
2. Создать Kubernetes Secret:
   ```bash
   kubectl create secret generic exchange-api-secret \
     --from-literal=api-key=YOUR_KEY_HERE
   ```
3. В `deployment.yaml` раскомментировать блок `secretKeyRef` в секции `env`.
4. Установить переменную окружения:
   ```bash
   kubectl set env deployment/currency-service USE_EXTERNAL_API=true
   ```

---

## 6. API Reference

| Метод | Endpoint            | Параметры        | Описание                        |
|-------|---------------------|------------------|---------------------------------|
| GET   | `/rate`             | `from`, `to`     | Курс валютной пары              |
| GET   | `/rates`            | —                | Все доступные пары              |
| GET   | `/health`           | —                | Liveness probe                  |
| GET   | `/docs`             | —                | Swagger UI                      |

Пример ответа `/rate?from=USD&to=RUB`:
```json
{"from": "USD", "to": "RUB", "rate": 92.5}
```

---

## 7. Контрольные вопросы

### Чем отличаются Deployment от StatefulSet?

| Характеристика        | Deployment                              | StatefulSet                                |
|-----------------------|-----------------------------------------|--------------------------------------------|
| Идентификаторы подов  | Случайные (pod-abc123)                  | Предсказуемые (pod-0, pod-1, pod-2)        |
| Хранилище (PVC)       | Общие тома или ephemeral                | Уникальный PVC на каждый под               |
| Порядок запуска       | Параллельный                            | Строго последовательный (0 → 1 → 2)        |
| DNS-имена подов       | Нет стабильных имён                     | Стабильные DNS: pod-0.svc.ns.svc.cluster.local |
| Применение            | Stateless сервисы (API, web-серверы)    | Stateful: БД (PostgreSQL, Kafka, Redis)    |

**Вывод:** `Deployment` используется для stateless приложений, где поды взаимозаменяемы.  
`StatefulSet` нужен, когда каждый под имеет уникальную идентичность и/или постоянное хранилище.

---

### Как Terraform управляет состоянием (state)?

Terraform хранит состояние развёрнутой инфраструктуры в файле `terraform.tfstate` (JSON).  
Механизм работы:

1. **`terraform plan`** — сравнивает `tfstate` с реальным состоянием и описанием в `.tf`-файлах, формирует diff.
2. **`terraform apply`** — применяет изменения и обновляет `tfstate`.
3. **`terraform destroy`** — удаляет ресурсы и очищает `tfstate`.

Для командной работы `tfstate` хранят удалённо (remote backend):
```hcl
terraform {
  backend "s3" {
    bucket = "my-tf-state"
    key    = "currency-service/terraform.tfstate"
    region = "us-east-1"
  }
}
```
Блокировка (locking) предотвращает одновременное изменение state несколькими пользователями.

---

### Какие шаги нужно добавить для внешнего API с секретным ключом?

1. **Создать Kubernetes Secret** (не хранить ключ в коде или YAML):
   ```bash
   kubectl create secret generic exchange-api-secret \
     --from-literal=api-key=<YOUR_KEY>
   ```
   Или через Terraform:
   ```hcl
   resource "kubernetes_secret" "api_key" {
     metadata { name = "exchange-api-secret" }
     data = { api-key = var.exchange_api_key }
   }
   ```

2. **Передать Secret в Pod через переменную окружения:**
   ```yaml
   env:
     - name: EXCHANGE_API_KEY
       valueFrom:
         secretKeyRef:
           name: exchange-api-secret
           key: api-key
     - name: USE_EXTERNAL_API
       value: "true"
   ```

3. **Добавить `EXCHANGE_API_KEY` в `.gitignore`** и никогда не коммитить `.env`-файлы.

4. **Для продакшна** — использовать Vault (HashiCorp) или облачные сервисы (AWS Secrets Manager, Azure Key Vault) для ротации ключей.

---

## Переменные окружения приложения

| Переменная         | Значение по умолчанию | Описание                              |
|--------------------|-----------------------|---------------------------------------|
| `USE_EXTERNAL_API` | `false`               | Использовать внешний API вместо mock  |
| `EXCHANGE_API_KEY` | `""`                  | API-ключ для ExchangeRate-API         |

