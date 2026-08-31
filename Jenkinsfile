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
                bat '.venv\\Scripts\\python -m playwright install'
            }
        }

        stage('Prepare Allure Metadata') {
            steps {
                bat 'if not exist reports\\allure-results mkdir reports\\allure-results'
                script {
                    def envText = "Environment=${params.ENV}\n" +
                        "Browser=${params.BROWSER}\n" +
                        "Framework=Playwright\n" +
                        "TestFramework=Pytest\n" +
                        "AI=Ollama\n" +
                        "CI=Jenkins\n"
                    writeFile file: 'reports/allure-results/environment.properties', text: envText
                }
            }
        }

        stage('Run Tests') {
            steps {
                bat '.venv\\Scripts\\python -m pytest --alluredir=reports/allure-results'
            }
        }

        stage('Publish Allure Report') {
            steps {
                script {
                    if (fileExists('reports/allure-results')) {
                        allure includeProperties: false, jdk: '', results: [[path: 'reports/allure-results']]
                    } else {
                        echo 'No Allure results found - skipping report publish.'
                    }
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true
        }
    }
}
