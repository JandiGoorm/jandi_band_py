pipeline {
    agent any
    
    environment {
        GITHUB_CREDENTIALS = credentials('github-credentials')
    }
    
    stages {
        stage('Checkout') {
            steps {
                git branch: 'main', 
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
                        
                        cd /home/ubuntu/flask-app
                        echo "Changed to flask-app directory"
                        
                        echo "Stopping existing containers..."
                        docker-compose down || true
                        
                        echo "Building new image using Dockerfile from workspace..."
                        docker build -t flask-scraper ${WORKSPACE}
                        
                        echo "Starting new container..."
                        docker-compose up -d
                        
                        echo "Waiting for service to start..."
                        sleep 30
                        
                        echo "Health check..."
                        curl -f http://localhost:5001/timetable?url=test || exit 1
                        
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
        }
        failure {
            echo 'Flask Scraper Pipeline failed!'
        }
        always {
            cleanWs()
        }
    }
} 