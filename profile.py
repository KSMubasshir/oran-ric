#!/usr/bin/env python

import geni.portal as portal
import geni.rspec.pg as RSpec
import geni.rspec.igext as IG
# Emulab specific extensions.
import geni.rspec.emulab as emulab
from lxml import etree as ET
import crypt
import random
import os
import hashlib
import os.path
import sys

TBCMD = "sudo mkdir -p /local/setup && sudo chown `geni-get user_urn | cut -f4 -d+` /local/setup && sudo -u `geni-get user_urn | cut -f4 -d+` -Hi /bin/bash -c '/local/repository/setup-driver.sh >/local/logs/setup.log 2>&1'"

#
# For now, disable the testbed's root ssh key service until we can remove ours.
# It seems to race (rarely) with our startup scripts.
#
disableTestbedRootKeys = True

#
# Create our in-memory model of the RSpec -- the resources we're going
# to request in our experiment, and their configuration.
#
rspec = RSpec.Request()

#
# This geni-lib script is designed to run in the CloudLab Portal.
#
pc = portal.Context()

#
# Define simplified parameters for O-RAN connectivity.
#
pc.defineParameter(
    "nodeCount","Number of Nodes",
    portal.ParameterType.INTEGER,1,
    longDescription="Number of nodes in your kubernetes cluster. For simplified O-RAN deployment, use 1 node.")
pc.defineParameter(
    "nodeType","Hardware Type",
    portal.ParameterType.NODETYPE,"d430",
    longDescription="Hardware type for the O-RAN node. d430 or d740 recommended.")
pc.defineParameter(
    "ricRelease","O-RAN SC RIC Release",
    portal.ParameterType.STRING,"h-release",
    [("h-release","h-release (e2ap v2)"),("g-release","g-release (e2ap v2)")],
    longDescription="O-RAN SC RIC component version for E2 agent compatibility.")
pc.defineParameter(
    "installVNC","Install VNC",
    portal.ParameterType.BOOLEAN,False,
    longDescription="Install VNC for remote desktop access.")
pc.defineParameter(
    "installORANSC","Install O-RAN SC RIC",
    portal.ParameterType.BOOLEAN,True,
    longDescription="Install the essential O-RAN SC RIC components for E2 connectivity.")
# Shared VLAN Configuration for srsRAN connectivity
pc.defineParameter(
    "sharedVlanName","Shared VLAN Name",
    portal.ParameterType.STRING,"",
    longDescription="Name of shared VLAN to connect with srsRAN handover experiment. Must match the VLAN name in your srsRAN experiment.")
pc.defineParameter(
    "sharedVlanAddress","O-RAN Gateway IP Address", 
    portal.ParameterType.STRING,"10.254.254.1",
    longDescription="IP address for this O-RAN node on the shared VLAN. This should be the gateway address configured in the srsRAN experiment.")
pc.defineParameter(
    "sharedVlanNetmask","Shared VLAN Netmask",
    portal.ParameterType.STRING,"255.255.255.0",
    longDescription="Subnet mask for the shared VLAN interface.")
# Essential configuration parameters
pc.defineParameter(
    "diskImage","Disk Image",
    portal.ParameterType.STRING,
    "urn:publicid:IDN+emulab.net+image+emulab-ops//UBUNTU22-64-STD",
    advanced=True,
    longDescription="Ubuntu 22 image for O-RAN deployment.")
pc.defineParameter(
    "publicIPCount", "Number of public IP addresses",
    portal.ParameterType.INTEGER,1,
    longDescription="Number of public IPs for accessing O-RAN services.",
    advanced=True)
# No complex datasets needed for simplified O-RAN

#
# Get any input parameter values that will override our defaults.
#
params = pc.bindParameters()

if params.publicIPCount > 8:
    perr = portal.ParameterWarning(
        "You cannot request more than 8 public IP addresses!",
        ["publicIPCount"])
    pc.reportWarning(perr)

if params.nodeCount > 1:
    perr = portal.ParameterWarning(
        "This simplified O-RAN profile is designed for single-node deployment. Multi-node may not work as expected.",
        ["nodeCount"])
    pc.reportWarning(perr)

#
# Give the library a chance to return nice JSON-formatted exception(s) and/or
# warnings; this might sys.exit().
#
pc.verifyParameters()

#
# General kubernetes instruction text.
#
kubeInstructions = \
  """
## Waiting for your Experiment to Complete Setup

Once the initial phase of experiment creation completes (disk load and node configuration), the profile's setup scripts begin the complex process of installing software according to profile parameters, so you must wait to access software resources until they complete.  The Kubernetes dashboard link will not be available immediately.  There are multiple ways to determine if the scripts have finished.
  - First, you can watch the experiment status page: the overall State will say \"booted (startup services are still running)\" to indicate that the nodes have booted up, but the setup scripts are still running.
  - Second, the Topology View will show you, for each node, the status of the startup command on each node (the startup command kicks off the setup scripts on each node).  Once the startup command has finished on each node, the overall State field will change to \"ready\".  If any of the startup scripts fail, you can mouse over the failed node in the topology viewer for the status code.
  - Third, the profile configuration scripts send emails: one to notify you that profile setup has started, and another notify you that setup has completed.
  - Finally, you can view [the profile setup script logfiles](http://{host-node-0}:7999/) as the setup scripts run.  Use the `admin` username and the automatically-generated random password `{password-adminPass}` .  This URL is available very quickly after profile setup scripts begin work.

## Kubernetes credentials and dashboard access

Once the profile's scripts have finished configuring software in your experiment, you'll be able to visit [the Kubernetes Dashboard WWW interface](https://{host-node-0}:8080/api/v1/namespaces/kube-system/services/https:kubernetes-dashboard:/proxy/#!/login) (approx. 10-15 minutes for the Kubernetes portion alone).

The easiest login option is to use token authentication.  (Basic auth is configured if available, for older kubernetes versions, username `admin` password `{password-adminPass}`.  You may also supply a kubeconfig file, but we don't provide one that includes a secret by default, so you would have to generate that.)

For `token` authentication: copy the token from http://{host-node-0}:7999/admin-token.txt (username `admin`, password `{password-adminPass}`) (this file is located on `node-0` in `/local/setup/admin-token.txt`).

(To provide secure dashboard access, we run a `kube-proxy` instance that listens on localhost:8888 and accepts all incoming hosts, and export that via nginx proxy listening on `{host-node-0}:8080` (but note that the proxy is restricted by path to the dashboard path only, so you cannot use this more generally).  We also create an `admin` `serviceaccount` in the `default` namespace, and that is the serviceaccount associated with the token auth option mentioned just above.)
 
Kubernetes credentials are in `~/.kube/config`, or in `/root/.kube/config`, as you'd expect.

## Changing your Kubernetes deployment

The profile's setup scripts are automatically installed on each node in `/local/repository`, and all of the Kubernetes installation is triggered from `node-0`.  The scripts execute as your uid, and keep state and downloaded files in `/local/setup/`.  The scripts write copious logfiles in that directory; so if you think there's a problem with the configuration, you could take a quick look through these logs on the `node-0` node.  The primary logfile is `/local/logs/setup.log`.

Kubespray is a collection of Ansible playbooks, so you can make changes to the deployed kubernetes cluster, or even destroy and rebuild it (although you would then lose any of the post-install configuration we do in `/local/repository/setup-kubernetes-extra.sh`).  The `/local/repository/setup-kubespray.sh` script installs Ansible inside a Python 3 `virtualenv` (in `/local/setup/kubespray-virtualenv` on `node-0`).  A `virtualenv` (or `venv`) is effectively a separate part of the filesystem containing Python libraries and scripts, and a set of environment variables and paths that restrict its user to those Python libraries and scripts.  To modify your cluster's configuration in the Kubespray/Ansible way, you can run commands like these (as your uid):

1. "Enter" (or access) the `virtualenv`: `. /local/setup/kubespray-virtualenv/bin/activate`
2. Leave (or remove the environment vars from your shell session) the `virtualenv`: `deactivate`
3. Destroy your entire kubernetes cluster: `ansible-playbook -i /local/setup/inventories/emulab/inventory.ini /local/setup/kubespray/remove-node.yml -b -v --extra-vars "node=node-0,node-1,node-2"`
   (note that you would want to supply the short names of all nodes in your experiment)
4. Recreate your kubernetes cluster: `ansible-playbook -i /local/setup/inventories/emulab/inventory.ini /local/setup/kubespray/cluster.yml -b -v`

To change the Ansible and playbook configuration, you can start reading Kubespray documentation:
  - https://github.com/kubernetes-sigs/kubespray/blob/master/docs/getting-started.md
  - https://github.com/kubernetes-sigs/kubespray
  - https://kubespray.io/
"""

#
# Customizable area for forks.
#
tourDescription = \
  "Simplified O-RAN profile for connecting to srsRAN handover experiments via shared VLAN. This profile deploys only the essential O-RAN SC Near-RT RIC components needed for E2 agent connectivity and basic xApp functionality."

oranHeadInstructions = \
  """
## Simplified O-RAN for srsRAN Handover Integration

This simplified O-RAN profile deploys essential O-RAN SC Near-RT RIC components to connect with srsRAN handover experiments via shared VLAN.

### Setup Process
1. **Deploy this O-RAN experiment first** with a shared VLAN name
2. **Deploy your srsRAN handover experiment** using the same shared VLAN name
3. **Wait for setup completion** (approximately 20-25 minutes)
4. **Get E2Term service IP** for srsRAN configuration

### Key Components Deployed
- **O-RAN SC RIC Platform**: Core RIC services (e2term, e2mgr, submgr, rtmgr)
- **Kubernetes cluster**: Single-node cluster for RIC components  
- **Shared VLAN connectivity**: Network bridge to srsRAN experiment
- **Essential xApps**: Basic monitoring and control applications

### Connecting to srsRAN Experiment

Once both experiments are running:

1. **Get the E2Term SCTP service IP** (needed for srsRAN eNodeB):
   ```bash
   kubectl get svc -n ricplt --field-selector metadata.name=service-ricplt-e2term-sctp-alpha -o jsonpath='{.items[0].spec.clusterIP}'
   ```

2. **Use this IP in your srsRAN eNodeB** (in the srsRAN experiment):
   ```bash
   sudo srsenb --ric.agent.remote_ipv4_addr=${E2TERM_IP} --log.all_level=warn --ric.agent.log_level=debug --log.filename=stdout
   ```

### Verification
- Check RIC pod status: `kubectl get pods -n ricplt`
- Monitor E2 connections: `kubectl logs -f -n ricplt -l app=ricplt-e2term-alpha`
- View connected eNodeBs: `kubectl logs -f -n ricplt -l app=ricplt-e2mgr`

"""

oranTailInstructions = \
  """

## O-RAN Deployment Details

This simplified profile deploys O-RAN SC RIC using standard [install scripts](http://gerrit.o-ran-sc.org/r/it/dep) with minimal configuration for srsRAN connectivity.

**Kubernetes Namespaces Created:**
- `ricplt`: Platform components (e2term, e2mgr, submgr, rtmgr, appmgr)  
- `ricinfra`: Infrastructure services (dbaas, jaegeradapter)
- `ricxapp`: xApplication deployment namespace

## Essential O-RAN Operations

### Monitoring RIC Components

Monitor core RIC services to verify connectivity:

```bash
# Check all RIC pods status
kubectl get pods -n ricplt

# Monitor E2 termination service (where eNodeBs connect)
kubectl logs -f -n ricplt -l app=ricplt-e2term-alpha

# Monitor E2 manager (shows connected eNodeBs)  
kubectl logs -f -n ricplt -l app=ricplt-e2mgr

# Check subscription manager
kubectl logs -f -n ricplt -l app=ricplt-submgr
```


### Getting E2Term Service Information

The key information needed for srsRAN connectivity:

```bash
# Get E2Term SCTP service IP (use this in srsRAN eNodeB configuration)
kubectl get svc -n ricplt --field-selector metadata.name=service-ricplt-e2term-sctp-alpha -o jsonpath='{.items[0].spec.clusterIP}'

# Get E2Term HTTP service IP (for xApp interactions)  
kubectl get svc -n ricplt --field-selector metadata.name=service-ricplt-e2term-alpha -o jsonpath='{.items[0].spec.clusterIP}'

# Check RIC platform health
kubectl get pods -n ricplt
kubectl get pods -n ricinfra  
kubectl get pods -n ricxapp
```

### Connecting srsRAN eNodeBs

Configure your srsRAN eNodeB (in the other experiment) to connect to this O-RAN RIC:

```bash
# In your srsRAN experiment, use the E2Term SCTP IP from above
sudo srsenb --ric.agent.remote_ipv4_addr=${E2TERM_IP} --log.all_level=warn --ric.agent.log_level=debug --log.filename=stdout
```

You should see E2SetupRequest and E2SetupResponse messages indicating successful RIC connection.

### O-RAN Management Commands

Essential commands for managing O-RAN services:

```bash
# Restart RIC core services if needed
kubectl -n ricplt rollout restart deployments/deployment-ricplt-e2term-alpha
kubectl -n ricplt rollout restart deployments/deployment-ricplt-e2mgr  
kubectl -n ricplt rollout restart deployments/deployment-ricplt-submgr

# Check service status  
kubectl get svc -n ricplt
kubectl get svc -n ricxapp

# Access Kubernetes dashboard (if needed)
# URL: https://{host-node-0}:8080/api/v1/namespaces/kube-system/services/https:kubernetes-dashboard:/proxy/#!/login
# Use token from: http://{host-node-0}:7999/admin-token.txt
```

### Troubleshooting

If eNodeBs cannot connect to RIC:
1. Check E2Term service is running: `kubectl get pods -n ricplt -l app=ricplt-e2term-alpha`
2. Verify shared VLAN connectivity between experiments
3. Check E2Term service IP is accessible from srsRAN nodes
4. Review E2Term logs: `kubectl logs -n ricplt -l app=ricplt-e2term-alpha`
"""

tourInstructions = oranHeadInstructions + kubeInstructions + oranTailInstructions

#
# Setup the Tour info with the above description and instructions.
#  
tour = IG.Tour()
tour.Description(IG.Tour.TEXT,tourDescription)
tour.Instructions(IG.Tour.MARKDOWN,tourInstructions)
rspec.addTour(tour)

if params.installVNC:
    rspec.initVNC()

datalans = []

# Simplified O-RAN uses single node, no data LAN needed

nodes = dict({})

# Create the single O-RAN node
node = RSpec.RawPC("node-0")
if params.nodeType:
    node.hardware_type = params.nodeType
if params.diskImage:
    node.disk_image = params.diskImage
if TBCMD is not None:
    node.addService(RSpec.Execute(shell="sh",command=TBCMD))
if disableTestbedRootKeys:
    node.installRootKeys(False, False)
if params.installVNC:
    node._ext_children.append(emulab.emuext.startVNC(nostart=True))

nodes["node-0"] = node

# Add shared VLAN interface if specified
sharedvlan = None
if params.sharedVlanName:
    iface = node.addInterface("ifSharedVlan")
    if params.sharedVlanAddress:
        iface.addAddress(RSpec.IPv4Address(params.sharedVlanAddress, params.sharedVlanNetmask))
    
    sharedvlan = RSpec.Link('shared-vlan-oran')
    sharedvlan.addInterface(iface)
    sharedvlan.createSharedVlan(params.sharedVlanName)
    sharedvlan.link_multiplexing = True
    sharedvlan.best_effort = True

# Add resources to RSpec
for nname in nodes.keys():
    rspec.addResource(nodes[nname])

# Add shared VLAN if configured
if sharedvlan is not None:
    rspec.addResource(sharedvlan)

class EmulabEncrypt(RSpec.Resource):
    def _write(self, root):
        ns = "{http://www.protogeni.net/resources/rspec/ext/emulab/1}"
        el = ET.SubElement(root,"%spassword" % (ns,),attrib={'name':'adminPass'})

adminPassResource = EmulabEncrypt()
rspec.addResource(adminPassResource)

#
# Grab a few public IP addresses.
#
apool = IG.AddressPool("node-0",params.publicIPCount)
rspec.addResource(apool)

pc.printRequestRSpec(rspec)
