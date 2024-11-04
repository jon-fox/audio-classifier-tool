# Credentials File
export AWS_SHARED_CREDENTIALS_FILE=/mnt/c/Users/foxj7/.aws/credentials
export AWS_CONFIG_FILE=/mnt/c/Users/foxj7/.aws/config

# PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:/mnt/c/Developer_Workspace/JusSkipIt_App"

export BASE_PATH=/mnt/c/Developer_Workspace/JusSkipIt_App/

# PYAUDIO
need to set ld lib path that includes already installed python-audio dependencies
so this venv can use it

export LD_LIBRARY_PATH=/usr/local/cuda-12.4/lib64:$LD_LIBRARY_PATH

# CICD
Github actions updated to wait for workflow dispatch from ui

# Terraform init
terraform init -backend-config="bucket=094d0cca-01db-472d-adc8-5eae88f51899"

# ecs agent
sudo yum install -y ecs-init
sudo systemctl start ecs

sudo systemctl status ecs 
 
# AMIs
#######################
this ami-092326650e967b14a is setup with nvidia drivers and docker

this ami-02e30e25d601cac67 is pre configured with nvidia, docker, and the jusskipit app container ready on ami in stopped state

# Updates for when working on Android App
10/28 added a bunch of commits for jusskipit switch in podcast ui
10/29 got the in app notification working when turning on jusskipit, need to get the icon to look like an uppercase 'J'
10/30 got the J working, now working on encompassing circle around the J
10/31 fixed the J image with gimp and png -> svg, svg resize, svg -> vector drawable
11/1 work on using playback manager
java/au/com/shiftyjelly/pocketcasts/repositories/playback/PlaybackManager.kt
added download jusskipit util class
11/2 fixed package dependency issues by moving class to same build dir
11/3 downloadutil compiling successfully, but not building correctly :/