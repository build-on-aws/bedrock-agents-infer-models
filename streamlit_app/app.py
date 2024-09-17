AWSTemplateFormatVersion: '2010-09-09'
Description: CloudFormation template to launch an EC2 instance with Streamlit application.

Parameters:
  InstanceType:
    Description: EC2 instance type
    Type: String
    Default: t3.small
    AllowedValues:
      - t3.small
      - t3.medium
      - t3.large
  MapPublicIpOnLaunch:
    Description: Enabled by default. Keep enabled for public IP assignment for EC2 instance connect
    Type: String
    Default: true
    AllowedValues:
      - false
      - true
  VPCCIDR:
    Description: VPC CIDR
    Type: String
    Default: 10.0.0.0/16
  VPCSubnet:
    Description: VPC CIDR
    Type: String
    Default: 10.0.1.0/24

Resources:
  # Create a VPC
  VPC:
    Type: 'AWS::EC2::VPC'
    Properties:
      CidrBlock: !Ref VPCCIDR
      Tags:
        - Key: Name
          Value: Bedrock-VPC

  # Create a Subnet within the VPC
  Subnet:
    Type: 'AWS::EC2::Subnet'
    Properties:
      VpcId: !Ref VPC
      CidrBlock: !Ref VPCSubnet
      MapPublicIpOnLaunch: !Ref MapPublicIpOnLaunch
      Tags:
        - Key: Name
          Value: Bedrock-Subnet

  # Create an Internet Gateway
  InternetGateway:
    Type: 'AWS::EC2::InternetGateway'
    Properties:
      Tags:
        - Key: Name
          Value: Bedrock-InternetGateway

  # Attach the Internet Gateway to the VPC
  AttachGateway:
    Type: 'AWS::EC2::VPCGatewayAttachment'
    Properties:
      VpcId: !Ref VPC
      InternetGatewayId: !Ref InternetGateway

  # Create a Route Table
  RouteTable:
    Type: 'AWS::EC2::RouteTable'
    Properties:
      VpcId: !Ref VPC
      Tags:
        - Key: Name
          Value: Bedrock-RouteTable

  # Create a Route in the Route Table to the Internet
  Route:
    Type: 'AWS::EC2::Route'
    DependsOn: AttachGateway
    Properties:
      RouteTableId: !Ref RouteTable
      DestinationCidrBlock: 0.0.0.0/0
      GatewayId: !Ref InternetGateway

  # Associate the Subnet with the Route Table
  SubnetRouteTableAssociation:
    Type: 'AWS::EC2::SubnetRouteTableAssociation'
    Properties:
      SubnetId: !Ref Subnet
      RouteTableId: !Ref RouteTable

  # Create a Security Group to allow HTTP traffic on port 8501 and SSH traffic
  InstanceSecurityGroup:
    Type: 'AWS::EC2::SecurityGroup'
    Properties:
      GroupDescription: Allow HTTP traffic on port 8501 and SSH traffic
      VpcId: !Ref VPC
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 8501
          ToPort: 8501
          CidrIp: 0.0.0.0/0
        - IpProtocol: tcp
          FromPort: 22
          ToPort: 22
          CidrIp: 18.237.140.160/29  # Restrict SSH access to a specific IP (CIDR for us-west-2)

  # Security Group Egress Rule
  InstanceSecurityGroupEgress:
    Type: 'AWS::EC2::SecurityGroupEgress'
    Properties:
      GroupId: !Ref InstanceSecurityGroup
      IpProtocol: -1
      FromPort: -1
      ToPort: -1
      CidrIp: 0.0.0.0/0

  # Create an IAM Role for the EC2 instance to use SSM and Amazon Bedrock
  EC2Role:
    Type: 'AWS::IAM::Role'
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: ec2.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/AmazonBedrockFullAccess
        - arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
        - arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess
        - arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess

  # Create an Instance Profile for the EC2 instance
  InstanceProfile:
    Type: 'AWS::IAM::InstanceProfile'
    Properties:
      Roles:
        - !Ref EC2Role

  # Create the EC2 instance
  EC2Instance:
    Type: 'AWS::EC2::Instance'
    Properties:
      InstanceType: !Ref InstanceType
      ImageId: !Sub "{{resolve:ssm:/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id}}"
      IamInstanceProfile: !Ref InstanceProfile
      SecurityGroupIds:
        - !Ref InstanceSecurityGroup
      SubnetId: !Ref Subnet
      EbsOptimized: true
      Monitoring: true
      Tags:
        - Key: Name
          Value: EC2-Streamlit-App
      UserData:
        Fn::Base64: !Sub |
          #!/bin/bash -xe
          exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1
          apt-get update -y
          apt-get upgrade -y
          apt-get install -y python3-pip git ec2-instance-connect
          git clone https://github.com/build-on-aws/bedrock-agents-infer-models.git /home/ubuntu/app
          pip3 install -r /home/ubuntu/app/streamlit_app/requirements.txt
          cd /home/ubuntu/app/streamlit_app

Outputs:
  InstanceId:
    Description: InstanceId of the newly created EC2 instance
    Value: !Ref EC2Instance
  
  PublicDnsName:
    Description: The public DNS name of the EC2 instance
    Value: !GetAtt EC2Instance.PublicDnsName




          


