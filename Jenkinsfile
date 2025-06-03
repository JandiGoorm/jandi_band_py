pipeline {
    agent any
    
    environment {
        GITHUB_CREDENTIALS = credentials('github-credentials')
        IMAGE_NAME = 'flask-scraper'
        CONTAINER_NAME = 'flask-scraper-app'
        HOST_PORT = '5001'
    }
    
    stages {
        stage('Checkout') {
            steps {
                git branch: 'master', 
                    credentialsId: 'github-credentials',
                    url: 'https://github.com/JandiGoorm/jandi_band_py.git'  // 실제 저장소 URL로 변경
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
                        docker run -d \
                            --name ${CONTAINER_NAME} \
                            --restart unless-stopped \
                            -p ${HOST_PORT}:5001 \
                            -e FLASK_ENV=production \
                            -e PYTHONUNBUFFERED=1 \
                            ${IMAGE_NAME}:latest
                        
                        echo "Waiting for service to start..."
                        sleep 30
                        
                        echo "Health check - Testing if service is responding..."
                        response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:${HOST_PORT}/health || echo "000")
                        echo "HTTP Response Code: $response"
                        
                        if [ "$response" = "200" ]; then
                            echo "✅ Service is responding correctly (HTTP $response)"
                        else
                            echo "❌ Service health check failed (HTTP $response)"
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
            echo 'Flask Scraper Pipeline succeeded!'
            sh 'docker logs ${CONTAINER_NAME} --tail 20'
        }
        failure {
            echo 'Flask Scraper Pipeline failed!'
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