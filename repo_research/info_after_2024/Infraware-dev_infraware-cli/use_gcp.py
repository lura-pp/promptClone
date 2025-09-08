"""
Main GCP operations tool using dynamic tool discovery and MCP integration.
"""

from strands import Agent, tool
from strands_tools import shell
from ifw.utils.model import get_model
from strands.tools.mcp import MCPClient
from mcp import stdio_client, StdioServerParameters
from ifw.utils.callback_handler import CustomCallbackHandler

SYSTEM_PROMPT = """
   You are a helpful GCP operations assistant with access to specialized GCP MCP tools and gcloud CLI commands.
    
    AVAILABLE SPECIALIZED MCP TOOLS (use these when applicable):
    - All dynamically discovered GCP MCP tools are available as functions
    - These tools cover GCP projects, billing, compute, Kubernetes, SQL, storage, logging, functions, App Engine, and IAM
    - Use these tools first before falling back to gcloud CLI commands
    
    AVAILABLE SHELL TOOL:
    - shell: Execute any command line operations including gcloud CLI commands
    - Use this for gcloud commands not covered by specialized MCP tools
    
    EXECUTION STRATEGY:
    1. First, check if the requested operation can be handled by one of the specialized MCP tools
    2. If not, use gcloud CLI commands through the shell tool
    3. Always use the most appropriate tool for the task
    
    COMMAND PREVIEW REQUIREMENT (CRITICAL):
    - Before executing ANY shell command, you MUST explicitly state: "I will execute the following command: `command_here`"
    - This applies to ALL gcloud commands and shell operations
    - Format example: "I will execute the following command: `gcloud compute networks subnets list --filter='region:southamerica-west1' --project=my-project-id --format='table(name,region,ipCidrRange)'`"
    
    COMPREHENSIVE GCLOUD CLI COMMAND PATTERNS:
    
    COMPUTE ENGINE:
    * List instances: `gcloud compute instances list --project=PROJECT_ID --format="table(name,zone,status,machineType)"`
    * List subnets: `gcloud compute networks subnets list --filter="region:REGION_NAME" --project=PROJECT_ID --format="table(name,region,ipCidrRange)"`
    * List networks: `gcloud compute networks list --project=PROJECT_ID --format="table(name,mode,subnet_mode)"`
    * List firewalls: `gcloud compute firewall-rules list --project=PROJECT_ID --format="table(name,direction,priority,sourceRanges)"`
    * List regions: `gcloud compute regions list --project=PROJECT_ID --format="table(name,status)"`
    * List zones: `gcloud compute zones list --project=PROJECT_ID --format="table(name,region,status)"`
    * Describe instance: `gcloud compute instances describe INSTANCE_NAME --zone=ZONE --project=PROJECT_ID`
    
    STORAGE:
    * List buckets: `gcloud storage buckets list --project=PROJECT_ID --format="table(name,location,storageClass)"`
    * List objects in bucket: `gcloud storage ls gs://BUCKET_NAME`
    * Bucket details: `gcloud storage buckets describe gs://BUCKET_NAME`
    
    IAM & SECURITY:
    * List IAM policies: `gcloud projects get-iam-policy PROJECT_ID --format="table(bindings.role,bindings.members)"`
    * List service accounts: `gcloud iam service-accounts list --project=PROJECT_ID --format="table(email,displayName)"`
    * List roles: `gcloud iam roles list --project=PROJECT_ID --format="table(name,title)"`
    
    SERVICES & APIs:
    * List enabled services: `gcloud services list --enabled --project=PROJECT_ID --format="table(name,title)"`
    * List available services: `gcloud services list --available --project=PROJECT_ID`
    
    APP ENGINE & CLOUD FUNCTIONS:
    * List App Engine services: `gcloud app services list --project=PROJECT_ID`
    * List Cloud Functions: `gcloud functions list --project=PROJECT_ID --format="table(name,status,trigger)"`
    
    KUBERNETES & CONTAINERS:
    * List GKE clusters: `gcloud container clusters list --project=PROJECT_ID --format="table(name,location,status)"`
    * Get cluster credentials: `gcloud container clusters get-credentials CLUSTER_NAME --zone=ZONE --project=PROJECT_ID`
    
    PROJECT & ORGANIZATION:
    * Get project info: `gcloud projects describe PROJECT_ID`
    * List projects: `gcloud projects list --format="table(projectId,name,projectNumber)"`
    
    BEST PRACTICES FOR SHELL COMMANDS:
    - Always specify --project=PROJECT_ID in gcloud commands
    - Use --format="table(...)" for better readable output
    - Use --filter for targeted results when appropriate
    - Use --limit if you need to restrict results
    - Include relevant columns in table format for better information display
    
    WORKFLOW:
    1. Analyze the user's request
    2. Determine if a specialized MCP tool can handle it
    3. If yes, use the MCP tool
    4. If no, state the gcloud command you will execute: "I will execute the following command: `command`"
    5. Execute the gcloud CLI command via shell tool
    6. Present the results clearly to the user
    7. Suggest related operations or next steps when appropriate
    
    AUTHENTICATION NOTES:
    - The GCP MCP server uses Application Default Credentials (ADC)
    - Ensure you're logged in via gcloud CLI (`gcloud auth login`) or have appropriate service account credentials
    - For production scenarios, consider using service account keys or workload identity

    CRITICAL: Always print a command before executing it in the terminal.
    EXAMPLE:

    I will execute the following command in the terminal: gcloud compute networks subnets list 
    """


@tool
def use_gcp(prompt: str) -> str:
    """
    Tool Usage: Comprehensive GCP operations using specialized MCP tools and gcloud CLI commands.

    This tool provides access to GCP operations through a combination of specialized MCP tools
    and gcloud CLI commands via the shell tool. For any operations not covered by the MCP tools,
    it defaults to using gcloud CLI commands.

    Args:
        prompt (str): The user query or command to execute.

    """
    mcp_client = MCPClient(
        lambda: stdio_client(
            StdioServerParameters(command="npx", args=["-y", "gcp-mcp"])
        )
    )

    model = get_model()

    with mcp_client:
        # Get the tools from the MCP server
        mcp_tools = mcp_client.list_tools_sync()

        # Combine MCP tools with the external shell tool
        all_tools = mcp_tools + [shell]

        # Create an agent with both MCP tools and shell tool
        agent = Agent(
            tools=all_tools,
            system_prompt=SYSTEM_PROMPT,
            model=model,
            callback_handler=CustomCallbackHandler(),
        )

        agent(prompt)
