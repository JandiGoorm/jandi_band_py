pipeline {
    agent any
    
    environment {
        GHCR_OWNER = 'kyj0503'
        IMAGE_NAME = 'jandi-band-py'
        DOCKER_BUILDKIT = '1'
    }
    
    stages {
        stage('Checkout') {
            steps {
                checkout([$class: 'GitSCM',
                    branches: [[name: '*/main'], [name: '*/master']],
                    userRemoteConfigs: [[
                        url: 'https://github.com/kyj0503/jandi_band_py.git',
                        credentialsId: 'github-token'
                    ]]
                ])
            }
        }

        stage('Login GHCR') {
            steps {
                script {
                    withCredentials([usernamePassword(credentialsId: 'github-token', usernameVariable: 'GITHUB_USER', passwordVariable: 'GITHUB_TOKEN')]) {
                        sh 'echo $GITHUB_TOKEN | docker login ghcr.io -u $GITHUB_USER --password-stdin'
                    }
                }
            }
        }
        
        stage('Build and Push Image') {
            steps {
                script {
                    def fullImageName = "ghcr.io/${env.GHCR_OWNER}/${env.IMAGE_NAME}"
                    
                    echo "Building Docker image: ${fullImageName}"
                    
                    // 빌드 및 푸시
                    sh """
                        docker build \
                            --tag ${fullImageName}:${env.BUILD_NUMBER} \
                            --tag ${fullImageName}:latest \
                            .
                        docker push ${fullImageName}:${env.BUILD_NUMBER}
                        docker push ${fullImageName}:latest
                    """
                }
            }
        }

        stage('Deploy') {
            steps {
                script {
                    sh '''
                        cd /opt/home-server/docker
                        docker compose -f docker-compose.apps.yml pull jandi-band-py
                        docker compose -f docker-compose.apps.yml up -d --no-deps --force-recreate jandi-band-py
                        sleep 5
                        docker ps | grep jandi-band-py
                        echo "✅ jandi-band-py deployment completed!"
                    '''
                }
            }
        }

        stage('Health Check') {
            steps {
                script {
                    sh '''
                        echo "Waiting for service to be ready..."
                        for i in 1 2 3 4 5 6; do
                            echo "Health check attempt $i/6"
                            if curl -sf https://rhythmeet-py.yeonjae.kr/health; then
                                echo "✅ Service is healthy!"
                                exit 0
                            fi
                            sleep 5
                        done
                        echo "⚠️ Health check timed out, but continuing..."
                    '''
                }
            }
        }
    }
    
    post {
        always {
            cleanWs()
        }
        success {
            echo '✅ jandi-band-py Build, Push, and Deploy completed successfully!'
        }
        failure {
            echo '❌ Pipeline failed!'
        }
    }
}
