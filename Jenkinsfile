pipeline {
    agent any

    parameters {
        choice(name: 'ENV', choices: ['qa', 'uat'], description: 'Target environment')
        choice(name: 'BROWSER', choices: ['chromium', 'firefox', 'webkit'], description: 'Browser to run tests against')
    }

    environment {
        ENV = "${params.ENV}"
        BROWSER = "${params.BROWSER}"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Setup Python Environment') {
            steps {
                bat 'python -m venv .venv'
                bat '.venv\\Scripts\\pip install -r requirements.txt'
                bat '.venv\\Scripts\\python -m playwright install --with-deps'
            }
        }

        stage('Run Tests') {
            steps {
                bat '.venv\\Scripts\\python -m pytest --alluredir=reports/allure-results'
            }
        }

        stage('Publish Allure Report') {
            steps {
                allure includeProperties: false, jdk: '', results: [[path: 'reports/allure-results']]
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true
        }
    }
}
