pipeline {
    agent any
    
    environment {
        GHCR_OWNER = 'kyj0503'
        EC2_HOST = 'rhythmeet-be.yeonjae.kr'
        EC2_USER = 'ubuntu'
        IMAGE_NAME = 'fastapi-scraper'
        CONTAINER_NAME = 'fastapi-scraper-app'
        HOST_PORT = '5001'
    }
    
    stages {
        // 1. 소스코드 내려받기
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        
        // 2. Docker 이미지 빌드 및 GHCR에 푸시
        stage('Build and Push to GHCR') {
            steps {
                script {
                    // 이미지 전체 경로 정의
                    def fullImageName = "ghcr.io/${env.GHCR_OWNER}/${env.IMAGE_NAME}:${env.BUILD_NUMBER}"
                    
                    echo "Building Docker image: ${fullImageName}"
                    docker.build(fullImageName, '.')

                    // Jenkins Credentials (ID: 'github-token')를 사용하여 GHCR에 로그인 및 푸시
                    docker.withRegistry("https://ghcr.io", 'github-token') {
                        echo "Pushing Docker image to GHCR..."
                        docker.image(fullImageName).push()
                    }
                }
            }
        }
        
        // 3. EC2 서버에 원격 배포
        stage('Deploy to EC2') {
            steps {
                script {
                    def fullImageName = "ghcr.io/${env.GHCR_OWNER}/${env.IMAGE_NAME}:${env.BUILD_NUMBER}"
                    
                    // Jenkins Credentials (ID: 'ec2-ssh-key')에 등록된 SSH 키 사용
                    withCredentials([sshUserPrivateKey(credentialsId: 'rhythmeet-ec2-ssh-key', keyFileVariable: 'EC2_PRIVATE_KEY')]) {
                        echo "Deploying to EC2 host: ${env.EC2_HOST}"
                        // EC2에 접속해서 deploy.sh 스크립트를 실행 (이미지 이름을 인자로 전달)
                        sh """
                            ssh -o StrictHostKeyChecking=no -i \${EC2_PRIVATE_KEY} ${env.EC2_USER}@${env.EC2_HOST} \
                            "bash /home/ubuntu/fastapi-app/deploy.sh ${fullImageName}"
                        """
                    }
                }
            }
        }
    }
    
    // post 블록: 빌드 성공/실패 시 EC2 서버의 컨테이너 상태를 확인
    post {
        success {
            echo 'FastAPI Scraper Pipeline succeeded!'
            script {
                // 성공 시 EC2 서버의 최신 로그 확인
                withCredentials([sshUserPrivateKey(credentialsId: 'rhythmeet-ec2-ssh-key', keyFileVariable: 'EC2_PRIVATE_KEY')]) {
                    sh """
                        ssh -o StrictHostKeyChecking=no -i \${EC2_PRIVATE_KEY} ${env.EC2_USER}@${env.EC2_HOST} \
                        "docker logs ${CONTAINER_NAME} --tail 20"
                    """
                }
            }
        }
        failure {
            echo 'FastAPI Scraper Pipeline failed!'
            script {
                // 실패 시 EC2 서버의 로그와 컨테이너 상태 확인
                 withCredentials([sshUserPrivateKey(credentialsId: 'rhythmeet-ec2-ssh-key', keyFileVariable: 'EC2_PRIVATE_KEY')]) {
                    sh """
                        ssh -o StrictHostKeyChecking=no -i \${EC2_PRIVATE_KEY} ${env.EC2_USER}@${env.EC2_HOST} \
                        "echo 'Container logs:'; docker logs ${CONTAINER_NAME} --tail 50 || true; echo 'Container status:'; docker ps -a | grep ${CONTAINER_NAME} || true"
                    """
                }
            }
        }
        always {
            // Jenkins 작업 공간 정리
            cleanWs()
        }
    }
}
