pipeline {
    agent any
    
    environment {
        GITHUB_CREDENTIALS = credentials('github-credentials')
        IMAGE_NAME = 'fastapi-scraper'
        CONTAINER_NAME = 'fastapi-scraper-app'
        HOST_PORT = '5001'
    }
    
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        
        stage('Build and Deploy') {
            steps {
                script {
                    sh '''
                        echo "Current workspace: ${WORKSPACE}"
                        echo "Checking Dockerfile existence..."
                        ls -la ${WORKSPACE}/Dockerfile
                        
                        echo "Working in Jenkins workspace directory"
                        cd ${WORKSPACE}
                        
                        echo "Stopping and removing existing container..."
                        docker stop ${CONTAINER_NAME} || true
                        docker rm ${CONTAINER_NAME} || true
                        
                        echo "Removing old image..."
                        docker rmi ${IMAGE_NAME}:latest || true
                        
                        echo "Building new image..."
                        docker build -t ${IMAGE_NAME}:latest .
                        
                        echo "Starting new container..."
                        docker run -d \\
                            --name ${CONTAINER_NAME} \\
                            --restart unless-stopped \\
                            -p ${HOST_PORT}:5001 \\
                            -e PYTHONUNBUFFERED=1 \\
                            ${IMAGE_NAME}:latest
                        
                        echo "Waiting for service to start..."
                        sleep 30
                        
                        echo "Health check - Testing if service is responding..."
                        
                        # 컨테이너 내부에서 직접 헬스체크 수행
                        if docker exec ${CONTAINER_NAME} curl -f http://localhost:5001/health > /dev/null 2>&1; then
                            echo "✅ Service is responding correctly"
                        else
                            echo "❌ Service health check failed"
                            echo "Checking if container is running..."
                            docker ps | grep ${CONTAINER_NAME} || true
                            echo "Container logs:"
                            docker logs ${CONTAINER_NAME} --tail 20 || true
                            exit 1
                        fi
                        
                        echo "Container status:"
                        docker ps | grep ${CONTAINER_NAME}
                        
                        echo "Cleaning up old images..."
                        docker image prune -f
                    '''
                }
            }
        }
    }
    
    post {
        success {
            echo 'FastAPI Scraper Pipeline succeeded!'
            sh 'docker logs ${CONTAINER_NAME} --tail 20'
        }
        failure {
            echo 'FastAPI Scraper Pipeline failed!'
            sh '''
                echo "Container logs:"
                docker logs ${CONTAINER_NAME} --tail 50 || true
                echo "Container status:"
                docker ps -a | grep ${CONTAINER_NAME} || true
            '''
        }
        always {
            cleanWs()
        }
    }
} 
