# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
from typing import Any, Optional
import json
import aws_cdk.aws_iam as aws_iam
import aws_cdk.aws_s3 as aws_s3
import aws_cdk.aws_stepfunctions as sfn
from aws_cdk import Aws, RemovalPolicy, Stack
from cdk_nag import NagPackSuppression, NagSuppressions
from constructs import Construct

_logger: logging.Logger = logging.getLogger(__name__)


class MLOPSSFNResources(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        project_name: str,
        deployment_name: str,
        module_name: str,
        bucket_policy_arn: Optional[str] = None,
        permission_boundary_arn: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        # MLOPS Env vars
        self.deployment_name = deployment_name
        self.module_name = module_name

        super().__init__(
            scope,
            id,
            description="This stack deploys Example DAGs resources for MLOps",
            **kwargs,
        )
        dep_mod = f"{project_name}-{deployment_name}-{module_name}"
        account: str = Aws.ACCOUNT_ID
        region: str = Aws.REGION

        mlops_assets_bucket = aws_s3.Bucket(
            self,
            id="mlops-sfn-assets-bucket",
            versioned=False,
            bucket_name=f"{dep_mod}-{account}-{region}",
            removal_policy=RemovalPolicy.DESTROY,
            encryption=aws_s3.BucketEncryption.KMS_MANAGED,
            block_public_access=aws_s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
        )

        self.mlops_assets_bucket = mlops_assets_bucket

        # Create Dag IAM Role and policy
        dag_statement = aws_iam.PolicyDocument(
            statements=[
                aws_iam.PolicyStatement(
                    actions=["s3:List*", "s3:Get*", "s3:Put*"],
                    effect=aws_iam.Effect.ALLOW,
                    resources=[
                        mlops_assets_bucket.bucket_arn,
                        f"{mlops_assets_bucket.bucket_arn}/*",
                    ],
                )
            ]
        )

        managed_policies = (
            [
                aws_iam.ManagedPolicy.from_managed_policy_arn(
                    self, "bucket-policy", bucket_policy_arn
                )
            ]
            if bucket_policy_arn
            else []
        )

        # Role with Permission Boundary
        r_name = f"mlops-{self.deployment_name}-{self.module_name}-role"
        # Create the Step Functions Execution Role

        sfn_exec_role = aws_iam.Role(
            self,
            "StepFunctionsExecutionRole",
            assumed_by=aws_iam.ServicePrincipal("states.amazonaws.com"),
            managed_policies=[
                aws_iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaRole"
                ),
                aws_iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSageMakerFullAccess"
                ),
                aws_iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonS3ReadOnlyAccess"
                ),
            ],
        )

        self.sfn_exec_role = sfn_exec_role

        # Define the IAM role
        sagemaker_execution_role = aws_iam.Role(
            self,
            "SageMakerExecutionRole",
            assumed_by=aws_iam.ServicePrincipal("sagemaker.amazonaws.com"),
            managed_policies=[
                aws_iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSageMakerFullAccess"
                )
            ],
            path="/",
            role_name=f"SageMakerExecutionRole-{self.stack_name}",
        )

        # Add policy to allow access to S3 bucket and IAM pass role
        mlops_assets_bucket.grant_read_write(sagemaker_execution_role)
        mlops_assets_bucket.grant_read(sfn_exec_role)
        sagemaker_execution_role.grant_pass_role(sfn_exec_role)

        self.sagemaker_execution_role = sagemaker_execution_role

        # Load the JSON state file

        with open("state_machine.json", "r") as file:
            state_machine_definition = json.load(file)

        # Create the Step Functions State Machine
        state_machine = sfn.StateMachine(
            self, "StateMachine",
            definition=state_machine_definition,
            state_machine_type=sfn.StateMachineType.STANDARD,
            role=sfn_exec_role
        )

        NagSuppressions.add_resource_suppressions(
            self,
            apply_to_children=True,
            suppressions=[
                NagPackSuppression(
                    id="AwsSolutions-S1",
                    reason="Logs are disabled for demo purposes",
                ),
                NagPackSuppression(
                    id="AwsSolutions-S5",
                    reason="No OAI needed - no one is accessing this data without explicit permissions",
                ),
                NagPackSuppression(
                    id="AwsSolutions-IAM5",
                    reason="Resource access restricted to MLOPS resources.",
                ),
                NagPackSuppression(
                    id="AwsSolutions-IAM4",
                    reason="Managed Policies are for service account roles only",
                ),
            ],
        )
