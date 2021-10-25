"""
Custom rules for cfn-lint
"""


import copy
import logging
import re
from cfnlint.rules import CloudFormationLintRule, RuleMatch # pylint: disable=import-error


LOGGER = logging.getLogger(__name__)


class MandatoryParametersRule(CloudFormationLintRule):
    """
    Check for Mandatory CloudFormation Parameters
    """

    id = "E9000"
    shortdesc = "Mandatory Parameters"
    description = "Ensuring that mandatory parameters are present"
    tags = ["ecommerce", "parameters"]

    _mandatory_parameters = ["Environment"]
    _message = "Missing parameter '{}'"

    def match(self, cfn):
        """
        Match missing mandatory parameters
        """

        mandatory_parameters = copy.deepcopy(self._mandatory_parameters)

        for key in cfn.get_parameters().keys():
            if key in mandatory_parameters:
                mandatory_parameters.remove(key)

        return [
            RuleMatch(["Parameters"], self._message.format(param))
            for param in mandatory_parameters
        ]


class Python39Rule(CloudFormationLintRule):
    """
    Check for Python3.9 usage
    """

    id = "E9001"
    shortdesc = "Python3.9 Lambda usage"
    description = "Ensure that Python3.9 is used by all Lambda functions"
    tags = ["ecommerce", "lambda"]

    _runtime = "python3.9"
    _message = "Function is using {} runtime instead of {}"

    def match(self, cfn):
        """
        Match against Lambda functions not using python3.9
        """

        matches = []

        for key, value in cfn.get_resources(["AWS::Lambda::Function"]).items():
            if value.get("Properties").get("Runtime") != self._runtime:
                matches.append(RuleMatch(
                    ["Resources", key],
                    self._message.format(value.get("Properties").get("Runtime"), self._runtime)
                ))

        return matches


class LambdaLogGroupRule(CloudFormationLintRule):
    """
    Check that all Lambda functions have a Log Group
    """

    id = "E9002"
    shortdesc = "Lambda Log group"
    description = "Ensure that all Lambda functions have a corresponding Log Group"

    tags = ["ecommerce", "lambda"]

    _message = "Function {} does not have a corresponding log group"

    def match(self, cfn):
        """
        Match functions that don't have a log group
        """

        matches = []

        functions = cfn.get_resources("AWS::Lambda::Function")
        log_groups = cfn.get_resources("AWS::Logs::LogGroup")

        known = []

        # Scan log groups for resource names
        for resource in log_groups.values():
            # This use an autogenerated log group name
            if "LogGroupName" not in resource.get("Properties"):
                continue

            log_group_name = resource.get("Properties").get("LogGroupName")
            # This doesn't have a !Sub transformation
            if not isinstance(log_group_name, dict) or "Fn::Sub" not in log_group_name:
                continue

            match = re.search(r"\${(?P<func>[^}]+)}", log_group_name["Fn::Sub"])
            if match is not None:
                known.append(match["func"])

        # Scan functions against log groups
        for function in functions.keys():
            if function not in known:
                matches.append(RuleMatch(
                    ["Resources", function],
                    self._message.format(function)
                ))

        return matches


class LambdaESMDestinationConfig(CloudFormationLintRule):
    """
    Check that Lambda Event Source Mapping have a DestinationConfig with OnFailure destination
    """

    id = "E9003"
    shortdesc = "Lambda EventSourceMapping OnFailure"
    description = "Ensure that Lambda Event Source Mapping have a DestinationConfig with OnFailure destination"

    _message = "Event Source Mapping {} does not have a DestinationConfig with OnFailure destination"

    def match(self, cfn):
        """
        Match EventSourceMapping that don't have a DestinationConfig with OnFailure
        """

        matches = []

        sources = cfn.get_resources("AWS::Lambda::EventSourceMapping")

        # Scan through Event Source Mappings
        for key, resource in sources.items():
            if resource.get("Properties", {}).get("DestinationConfig", {}).get("OnFailure", None) is None:
                matches.append(RuleMatch(
                    ["Resources", key],
                    self._message.format(key)
                ))

        return matches

class LambdaRuleInvokeConfig(CloudFormationLintRule):
    """
    Check that Lambda functions invoked by EventBridge have a corresponding EventInvokeConfig
    """

    id = "E9004"
    shortdesc = "Lambda EventBridge OnFailure"
    description = "Ensure that Lambda functions invoked by EventBring have an Event Invoke Config with OnFailure destination"

    _message = "Rule {} does not have a corresponding Event Invoke Config with OnFailure destination"

    def match(self, cfn):
        """
        Match Events Rules that don't have a corresponding EventInvokeConfig
        """

        matches = []

        function_names = cfn.get_resources("AWS::Lambda::Function").keys()
        rules = cfn.get_resources("AWS::Events::Rule")
        invoke_configs = cfn.get_resources("AWS::Lambda::EventInvokeConfig")

        # Get the list of function names with EventInvokeConfig and OnFailure
        invoke_config_functions = []
        for resource in invoke_configs.values():
            if resource.get("Properties", {}).get("DestinationConfig", {}).get("OnFailure", None) is None:
                continue
            invoke_config_functions.append(resource["Properties"]["FunctionName"]["Ref"])

        # Parse rules
        for key, resource in rules.items():
            for target in resource.get("Properties", {}).get("Targets", []):
                if target.get("Arn", {}).get("Fn::GetAtt", None) is None:
                    continue

                if target["Arn"]["Fn::GetAtt"][0] not in function_names:
                    continue

                function_name = target["Arn"]["Fn::GetAtt"][0]
                if function_name not in invoke_config_functions:
                    matches.append(RuleMatch(
                        ["Resources", key],
                        self._message.format(key)
                    ))

        return matches


class LambdaInsightsLayer(CloudFormationLintRule):
    """
    Check that Lambda functions have the CloudWatch Lambda Insights Layer
    """

    id = "E9005"
    shortdesc = "Lambda Insights Layer"
    description = "Ensure that Lambda functions use the CloudWatch Lambda Insights Layer"

    _message = "Function {} does not use the CloudWatch Lambda Insights layer"
    _layer_pattern = { "Fn::Sub": "arn:aws:lambda:${AWS::Region}:580247275435:layer:LambdaInsightsExtension:2" }

    def match(self, cfn):
        """
        Match Lambda functions that don't have the Lambda Insights Layer
        """

        matches = []

        functions = cfn.get_resources("AWS::Lambda::Function")

        for key, resource in functions.items():
            if  self._layer_pattern not in resource.get("Properties", {}).get("Layers", []):
                matches.append(RuleMatch(
                    ["Resources", key],
                    self._message.format(key)
                ))

        return matches


class LambdaInsightsPermission(CloudFormationLintRule):
    """
    Check that Lambda functions have the CloudWatch Lambda Insights managed policy
    """

    id = "E9006"
    shortdesc = "Lambda Insights Permission"
    description = "Ensure that Lambda functions have the CloudWatch Lambda Insights managed policy"

    _message = "Function {} does not have the CloudWatch Lambda Insights managed policy"
    _policy_arn = "arn:aws:iam::aws:policy/CloudWatchLambdaInsightsExecutionRolePolicy"

    def match(self, cfn):
        """
        Match Lambda functions that don't have the right permission for CloudWatch Lambda Insights
        """

        matches = []

        function_names = cfn.get_resources("AWS::Lambda::Function").keys()
        roles = cfn.get_resources("AWS::IAM::Role")

        for function_name in function_names:
            if self._policy_arn not in roles[f"{function_name}Role"].get("Properties", {}).get("ManagedPolicyArns", []):
                matches.append(RuleMatch(
                    ["Resources", function_name],
                    self._message.format(function_name)
                ))

        return matches


class IAMPutEventsConditions(CloudFormationLintRule):
    """
    Check that IAM Roles with events:PutEvents action restrict based on event source
    """

    id = "E9007"
    shortdesct = "IAM PutEvents Condition"
    description = "Ensure that IAM roles with event:PutEvents action restrict based on event source"

    _message = "IAM role {} does not have an events:source condition for the events:PutEvents action"

    def _match_policy(self, policy) -> bool:
        """
        Match policies with events:PutEvents and no events:source condition
        """

        for statement in policy.get("PolicyDocument", {}).get("Statement", []):
            if "events:PutEvents" in statement.get("Action", {}):
                if not statement.get("Condition", {}).get("StringEquals", {}).get("events:source", None):
                    return True

        return False

    def match(self, cfn):
        """
        Match IAM roles that don't have conditions for events:PutEvents actions
        """

        matches = []

        roles = cfn.get_resources("AWS::IAM::Role")
        for role_name, role in roles.items():
            found = False
            for policy in role.get("Properties", {}).get("Policies", []):
                if self._match_policy(policy):
                    found = True

            if found:
                matches.append(RuleMatch(
                    ["Resources", role_name],
                    self._message.format(role_name)
                ))

        return matches