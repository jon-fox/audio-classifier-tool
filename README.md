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

ami-05f85bc16c1a0257a - latest for jusskipit_v2

# Updates for when working on Android App
11/28 issues using whisperx since ctranslate2 updates
