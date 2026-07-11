.PHONY: help start stop restart rebuild logs logs-infra logs-app clean status

help:
	@echo "EVOKE Prosperity - Make Commands"
	@echo ""
	@echo "  make start       Start infrastructure and app (in order)"
	@echo "  make stop        Stop all containers"
	@echo "  make restart     Restart all containers"
	@echo "  make rebuild     Force rebuild all images and start"
	@echo "  make logs        Show logs from all services"
	@echo "  make logs-infra  Show logs from infrastructure"
	@echo "  make logs-app    Show logs from app"
	@echo "  make status      Show container status"
	@echo "  make clean       Stop and remove all containers, networks, volumes"
	@echo ""

start: start-infra wait-infra start-app
	@echo "✅ EVOKE Prosperity is running!"
	@echo "📍 Access at: http://localhost:8000"

start-infra:
	@echo "🚀 Starting infrastructure..."
	cd evoke-infra && docker compose up -d
	@echo "⏳ Waiting for infrastructure to be healthy..."

wait-infra:
	@echo "⏳ Checking PostgreSQL..."
	@until docker compose -f evoke-infra/docker-compose.yml exec -T postgres pg_isready -U evoke > /dev/null 2>&1; do \
		echo "  Waiting for PostgreSQL..."; \
		sleep 2; \
	done
	@echo "✅ PostgreSQL ready"
	@echo "⏳ Checking Redpanda..."
	@until docker compose -f evoke-infra/docker-compose.yml exec -T redpanda rpk cluster health > /dev/null 2>&1; do \
		echo "  Waiting for Redpanda..."; \
		sleep 2; \
	done
	@echo "✅ Redpanda ready"
	@echo "⏳ Checking OpenSearch..."
	@until docker compose -f evoke-infra/docker-compose.yml exec -T opensearch curl -fs http://localhost:9200/_cluster/health > /dev/null 2>&1; do \
		echo "  Waiting for OpenSearch..."; \
		sleep 2; \
	done
	@echo "✅ OpenSearch ready"
	@echo "✅ Infrastructure healthy"

start-app:
	@echo "🚀 Starting EVOKE app..."
	cd evoke && docker compose up -d
	@echo "⏳ Waiting for app to start..."
	@until curl -fs http://localhost:8000/api/health > /dev/null 2>&1; do \
		echo "  Waiting for app..."; \
		sleep 2; \
	done
	@echo "✅ App is running"

stop:
	@echo "🛑 Stopping all services..."
	cd evoke && docker compose down
	cd evoke-infra && docker compose down
	@echo "✅ Stopped"

restart: stop start

rebuild: stop clean start-infra wait-infra
	@echo "🔨 Rebuilding app containers..."
	cd evoke && docker compose up -d --build
	@echo "⏳ Waiting for app to start..."
	@until curl -fs http://localhost:8000/api/health > /dev/null 2>&1; do \
		echo "  Waiting for app..."; \
		sleep 2; \
	done
	@echo "✅ Rebuild complete and running"

logs:
	@echo "📊 Tailing logs from all services..."
	docker compose -f evoke-infra/docker-compose.yml -f evoke/docker-compose.yml logs -f

logs-infra:
	@echo "📊 Tailing infrastructure logs..."
	cd evoke-infra && docker compose logs -f

logs-app:
	@echo "📊 Tailing app logs..."
	cd evoke && docker compose logs -f web

status:
	@echo "📊 Infrastructure containers:"
	cd evoke-infra && docker compose ps
	@echo ""
	@echo "📊 App containers:"
	cd evoke && docker compose ps

clean:
	@echo "🧹 Cleaning up all containers, networks, and volumes..."
	cd evoke && docker compose down -v
	cd evoke-infra && docker compose down -v
	@echo "✅ Cleaned"
