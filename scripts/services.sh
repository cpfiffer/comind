#!/bin/bash

# Comind Services Management Script
# Makes it easy to start different combinations of services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

show_help() {
    echo "Comind Services Management"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  start <profile>    Start services"
    echo "  stop <profile>     Stop services" 
    echo "  restart <profile>  Restart services"
    echo "  status             Show running services"
    echo "  logs <service>     Show logs for a service"
    echo "  shell              Connect to Neo4j shell"
    echo ""
    echo "Profiles:"
    echo "  database          Start only Neo4j database"
    echo "  inference         Start only inference services (LLM + embeddings)"
    echo "  all               Start all services"
    echo "  (no profile)      Start default services (database only)"
    echo ""
    echo "Examples:"
    echo "  $0 start database           # Start only Neo4j"
    echo "  $0 start inference          # Start only inference services"
    echo "  $0 start all                # Start everything"
    echo "  $0 start                    # Start default (database)"
    echo "  $0 logs neo4j               # Show Neo4j logs"
    echo "  $0 shell                    # Connect to Neo4j shell"
}

start_services() {
    local profile="$1"
    
    if [ -z "$profile" ]; then
        echo "Starting default services (database)..."
        docker-compose up -d
    else
        echo "Starting $profile services..."
        docker-compose --profile "$profile" up -d
    fi
    
    echo ""
    echo "Services started. Access points:"
    if [ "$profile" = "database" ] || [ "$profile" = "all" ] || [ -z "$profile" ]; then
        echo "  Neo4j Browser: http://localhost:7474"
        echo "  Neo4j Bolt: bolt://localhost:7687"
        echo "  Username: neo4j, Password: comind123"
    fi
    if [ "$profile" = "inference" ] || [ "$profile" = "all" ]; then
        echo "  LLM API: http://localhost:8002"
        echo "  Embeddings API: http://localhost:8001"
    fi
}

stop_services() {
    local profile="$1"
    
    if [ -z "$profile" ]; then
        echo "Stopping all services..."
        docker-compose down
    else
        echo "Stopping $profile services..."
        docker-compose --profile "$profile" down
    fi
}

restart_services() {
    local profile="$1"
    stop_services "$profile"
    start_services "$profile"
}

show_status() {
    echo "Running Comind services:"
    echo ""
    docker-compose ps
}

show_logs() {
    local service="$1"
    if [ -z "$service" ]; then
        echo "Error: Please specify a service name"
        echo "Available services: neo4j, srv-llm, embeddings"
        exit 1
    fi
    
    docker-compose logs -f "$service"
}

neo4j_shell() {
    echo "Connecting to Neo4j shell..."
    echo "Use 'MATCH (n) RETURN n LIMIT 10;' to test the connection"
    docker-compose exec neo4j cypher-shell -u neo4j -p comind123
}

# Main command handling
case "$1" in
    "start")
        start_services "$2"
        ;;
    "stop")
        stop_services "$2"
        ;;
    "restart")
        restart_services "$2"
        ;;
    "status")
        show_status
        ;;
    "logs")
        show_logs "$2"
        ;;
    "shell")
        neo4j_shell
        ;;
    "help"|"-h"|"--help"|"")
        show_help
        ;;
    *)
        echo "Error: Unknown command '$1'"
        echo ""
        show_help
        exit 1
        ;;
esac