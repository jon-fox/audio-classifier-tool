import boto3
import json

# export AWS_SHARED_CREDENTIALS_FILE=/mnt/c/Users/foxj7/.aws/credentials
# export AWS_CONFIG_FILE=/mnt/c/Users/foxj7/.aws/config

def get_parameter(name, with_decryption=True):
    ssm = boto3.client('ssm', region_name='us-east-1')
    response = ssm.get_parameter(
        Name=name,
        WithDecryption=with_decryption
    )
    return response['Parameter']['Value']


def print_env_vars():
    parameters = {
        "AWS_ACCOUNT_ID": "/account/account_id",
        "OPENAI_API_KEY": "/openai/api_key",
        "TADDY_CREDENTIALS": "/taddy/credentials",
    }

    for env_var, param_name in parameters.items():
        value = get_parameter(param_name)
        if param_name in ["/taddy/credentials", "/postgres/credentials", "/backblaze/credentials"]:
            for key, value in json.loads(value).items():    
                print(f"export {key.upper()}={value}")
        else:
            print(f"export {env_var}={value}")


if __name__ == "__main__":
    print_env_vars()
