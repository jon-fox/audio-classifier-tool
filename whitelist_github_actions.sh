# Fetch GitHub Actions IP ranges
GITHUB_IPS=$(curl -s https://api.github.com/meta | jq -r '.actions[]')

# Prefix List details
PREFIX_LIST_NAME="GitHubActionsPrefixList"
PREFIX_LIST_DESCRIPTION="Managed list of GitHub Actions IP ranges"
MAX_ENTRIES=100  # Max entries allowed in your prefix list (adjust as needed)

# Create the Prefix List if it doesn't exist
PREFIX_LIST_ID=$(aws ec2 create-managed-prefix-list \
  --prefix-list-name "$PREFIX_LIST_NAME" \
  --max-entries $MAX_ENTRIES \
  --address-family "IPv4" \
  --tag-specifications 'ResourceType=prefix-list,Tags=[{Key=Name,Value=GitHubActionsPrefixList}]' \
  --output text --query 'PrefixList.PrefixListId')

echo "Created or fetched Prefix List with ID: $PREFIX_LIST_ID"

# Get the latest version of the prefix list
LATEST_VERSION=$(aws ec2 describe-managed-prefix-lists \
  --prefix-list-ids $PREFIX_LIST_ID \
  --output text --query 'PrefixLists[0].Version')

echo "Latest Version of Prefix List: $LATEST_VERSION"

# Prepare IP list to be added
entry_number=0
for ip in $GITHUB_IPS; do
  # Check if the CIDR block ends with /16 (optional)
  if [[ "$ip" == */16 ]]; then
    # Add each entry to the prefix list using the latest version
    aws ec2 modify-managed-prefix-list \
      --prefix-list-id $PREFIX_LIST_ID \
      --current-version $LATEST_VERSION \
      --add-entries Cidr=$ip,Description="GitHub Actions IP $entry_number"
    echo "Added $ip to Prefix List"
    entry_number=$((entry_number+1))

    # Increment the version for the next modification
    LATEST_VERSION=$((LATEST_VERSION+1))
  fi
done

echo "Finished updating Prefix List with GitHub Actions IP ranges."
