echo "Please enter your AWS Account ID"
read accountid
echo "Please enter the AWS Region you wish to deploy the action on"
read region

sed -i -e "s/<<Region>>/${region}/g; s/<<AccountId>>/${accountid}/g" api_swagger_template.json