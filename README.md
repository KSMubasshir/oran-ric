# Simplified O-RAN Profile for srsRAN Integration

This profile provides a streamlined O-RAN SC Near-RT RIC deployment specifically designed for integration with srsRAN experiments via shared VLAN connectivity.

## Overview

This simplified O-RAN profile is a companion to the `srsepc-fbs-handover-with-oran` profile, enabling O-RAN E2 interface connectivity without the complexity of extensive demos and multi-node deployments.

### Key Features

- **Single-node deployment** - Minimal resource requirements
- **Essential O-RAN components** - Core RIC platform services only
- **Shared VLAN support** - Seamless connectivity with srsRAN experiments
- **E2 interface ready** - Pre-configured for srsRAN eNodeB connections
- **Simplified parameters** - Easy instantiation with essential options only

## Components Deployed

- **O-RAN SC RIC Platform** (ricplt namespace):
  - E2 Termination (e2term) - E2 interface endpoint
  - E2 Manager (e2mgr) - RAN node management
  - Subscription Manager (submgr) - E2 subscription handling
  - Routing Manager (rtmgr) - Message routing
  - Application Manager (appmgr) - xApp lifecycle management

- **Supporting Infrastructure** (ricinfra namespace):
  - Database services (dbaas)
  - Monitoring and logging components

- **Kubernetes cluster** - Single-node deployment for RIC services

## Usage Workflow

### 1. Deploy O-RAN Experiment

Create this O-RAN experiment first:
- Select hardware type (d740, d430-4, etc.)
- Choose shared VLAN name (e.g., `oran-handover-vlan`)
- Set O-RAN SC version (default: g-release)
- Wait ~20-25 minutes for deployment

### 2. Deploy srsRAN Handover Experiment  

Deploy your `srsepc-fbs-handover-with-oran` experiment:
- Use the **same shared VLAN name**
- Enable O-RAN integration parameters
- Configure E2 agent settings

### 3. Get E2Term Service IP

In the O-RAN experiment, get the E2Term service IP:

```bash
kubectl get svc -n ricplt --field-selector metadata.name=service-ricplt-e2term-sctp-alpha -o jsonpath='{.items[0].spec.clusterIP}'
```

### 4. Configure srsRAN eNodeB

In your srsRAN experiment, use the E2Term IP:

```bash
sudo srsenb --ric.agent.remote_ipv4_addr=${E2TERM_IP} --log.all_level=warn --ric.agent.log_level=debug
```

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `phystype_compute` | Hardware type for O-RAN node | `d740` |
| `node_compute_image` | OS image | `UBUNTU22-64-STD` |
| `shared_vlan` | VLAN name for srsRAN connectivity | (empty) |
| `kubernetes_version` | Kubernetes version | `1.26.15` |
| `oran_version` | O-RAN SC release | `g` |
| `ricplt_release` | RIC platform helm chart release | `3.0.1` |
| `ricaux_release` | RIC auxiliary components release | `3.0.0` |

## Verification Commands

### Check RIC Status
```bash
# All RIC platform pods
kubectl get pods -n ricplt

# E2 termination service (eNodeB connection point)
kubectl logs -f -n ricplt -l app=ricplt-e2term-alpha

# E2 manager (connected RAN nodes)
kubectl logs -f -n ricplt -l app=ricplt-e2mgr
```

### Monitor E2 Connections
```bash
# Watch for E2SetupRequest/Response messages
kubectl logs -f -n ricplt -l app=ricplt-e2term-alpha | grep -i e2setup

# Check subscription manager
kubectl logs -f -n ricplt -l app=ricplt-submgr
```

## Troubleshooting

### eNodeB Cannot Connect to RIC

1. **Check E2Term service**:
   ```bash
   kubectl get pods -n ricplt -l app=ricplt-e2term-alpha
   ```

2. **Verify shared VLAN connectivity**:
   - Ensure both experiments use same VLAN name
   - Check network connectivity between nodes

3. **Check E2Term logs**:
   ```bash
   kubectl logs -n ricplt -l app=ricplt-e2term-alpha
   ```

### RIC Services Not Starting

1. **Check pod status**:
   ```bash
   kubectl get pods -n ricplt -n ricinfra
   ```

2. **Restart core services**:
   ```bash
   kubectl -n ricplt rollout restart deployments/deployment-ricplt-e2term-alpha
   kubectl -n ricplt rollout restart deployments/deployment-ricplt-e2mgr
   ```

## Integration with srsRAN Handover Profile

This profile is designed to work with the enhanced `srsepc-fbs-handover-with-oran` profile:

- **Shared VLAN**: Both profiles must use the same VLAN name
- **E2 Agent**: srsRAN eNodeBs connect via E2 interface to this RIC
- **Network addressing**: RIC uses standard cluster networking, srsRAN uses configurable addressing
- **Monitoring**: Both profiles provide monitoring capabilities for E2 connections

## Resource Requirements

- **Minimum**: 1 node (d740 recommended)
- **CPU**: 16+ cores recommended for RIC platform
- **Memory**: 32GB+ recommended
- **Storage**: Standard disk image sufficient
- **Network**: Shared VLAN interface + management network

## Files Structure

```
oran/
├── profile.py          # Main geni-lib profile
└── README.md          # This documentation
```

## Related Profiles

- **srsepc-fbs-handover-with-oran**: Enhanced srsRAN handover testbed with O-RAN E2 agent support
- **srslte-shvlan-oran**: Full-featured srsLTE with comprehensive O-RAN integration

## Support

For issues with O-RAN deployment or srsRAN integration:
1. Check the troubleshooting section above
2. Review experiment logs via POWDER web interface  
3. Monitor RIC component logs using kubectl commands
4. Verify shared VLAN connectivity between experiments