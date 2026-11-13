pipeline {
  agent any

  triggers {
    cron('0 8 * * 1')
  }

  environment {
    OVERFAST_API_BASE_URL = 'https://overfast-api.tekrop.fr'
    PLAYER_IDS = 'CR33PRSWXXPR-1604'
    PLATFORM = 'pc'
    GAMEMODE = 'competitive'
    SPREADSHEET_ID = '131tdUKSHkx7iVSEGykTJuwhRDS0Web5-9jAvgsTl3LY'
    SHEET_NAME = 'Overwatch Weekly Updates'
  }

  stages {
    stage('Install dependencies') {
      steps {
        sh 'python3 -m pip install --upgrade pip'
        sh 'python3 -m pip install -r requirements.txt'
      }
    }

    stage('Write weekly OverFast snapshot') {
      steps {
        withCredentials([file(credentialsId: 'overwatch-gsheets-creds', variable: 'GOOGLE_SERVICE_ACCOUNT_FILE')]) {
          sh '''
            python3 scripts/overwatch_weekly_tracker.py \
              --players "$PLAYER_IDS" \
              --platform "$PLATFORM" \
              --gamemode "$GAMEMODE" \
              --spreadsheet-id "$SPREADSHEET_ID" \
              --sheet-name "$SHEET_NAME" \
              --service-account-file "$GOOGLE_SERVICE_ACCOUNT_FILE" \
              --api-base-url "$OVERFAST_API_BASE_URL"
          '''
        }
      }
    }
  }
}
