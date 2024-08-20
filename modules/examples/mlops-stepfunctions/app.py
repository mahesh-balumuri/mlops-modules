# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import aws_cdk
import cdk_nag
from aws_cdk import App
from pydantic import ValidationError

from settings import ApplicationSettings
from stack import MLOPSSFNResources

app = App()

try:
    app_settings = ApplicationSettings()
except ValidationError as e:
    print(e)
    raise e

stack = MLOPSSFNResources(
    scope=app,
    id=app_settings.seedfarmer_settings.app_prefix,
    project_name=app_settings.seedfarmer_settings.project_name,
    deployment_name=app_settings.seedfarmer_settings.deployment_name,
    module_name=app_settings.seedfarmer_settings.module_name,
    bucket_policy_arn=app_settings.module_settings.bucket_policy_arn,
    permission_boundary_arn=app_settings.module_settings.permission_boundary_arn,
    env=aws_cdk.Environment(
        account=app_settings.cdk_settings.account,
        region=app_settings.cdk_settings.region,
    ),
)

aws_cdk.CfnOutput(
    scope=stack,
    id="metadata",
    value=stack.to_json_string(
        {
            "MlOpsBucket": stack.mlops_assets_bucket.bucket_name,
            "SageMakerExecutionRole": stack.sagemaker_execution_role.role_arn,
        }
    ),
)

aws_cdk.Aspects.of(stack).add(cdk_nag.AwsSolutionsChecks(log_ignores=True))

if app_settings.module_settings.tags:
    for tag_key, tag_value in app_settings.module_settings.tags.items():
        aws_cdk.Tags.of(app).add(tag_key, tag_value)

aws_cdk.Tags.of(app).add("SeedFarmerDeploymentName", app_settings.seedfarmer_settings.deployment_name)
aws_cdk.Tags.of(app).add("SeedFarmerModuleName", app_settings.seedfarmer_settings.module_name)
aws_cdk.Tags.of(app).add("SeedFarmerProjectName", app_settings.seedfarmer_settings.project_name)

app.synth(force=True)
