---
excalidraw-plugin: parsed
tags: [excalidraw]
---

# Excalidraw Data

## Text Elements
Manual knowledge updates ^574dde50

An operator starts this workflow; user questions never trigger it. ^4ccae40d

Originals ^afc1dff9

Selected documents ^ef6bfb55

Prepare ^f5b36649

Extract + normalize ^248927d2

Prepared text ^f9501d46

GCS or local files ^54082fca

Qdrant ^53e85561

Rebuildable index ^16d3a26c

Chunk + embed ^4cee4136

BGE embeddings ^a4335385

%%
## Drawing
```json
{
  "elements": [
    {
      "isDeleted": false,
      "locked": false,
      "strokeColor": "transparent",
      "link": null,
      "roughness": 0.8,
      "groupIds": [],
      "index": "a0",
      "backgroundColor": "#ffffff",
      "angle": 0,
      "customData": {
        "codex": {
          "semanticId": "fireworks_background",
          "layoutRole": "background",
          "batchId": "nora_ingestion",
          "motion": false,
          "createdBy": "codex",
          "role": "background"
        }
      },
      "fillStyle": "solid",
      "strokeWidth": 1,
      "version": 2,
      "roundness": null,
      "type": "rectangle",
      "updated": 1789385858197,
      "id": "fw_nora_ingestion_background",
      "x": 0,
      "seed": 1351646733,
      "boundElements": [],
      "y": -20,
      "opacity": 100,
      "height": 660,
      "width": 1063,
      "frameId": null,
      "strokeStyle": "solid",
      "versionNonce": 838008877
    },
    {
      "seed": 491255107,
      "strokeStyle": "solid",
      "id": "574dde50",
      "strokeWidth": 1.5,
      "roughness": 0.2,
      "isDeleted": false,
      "fontSize": 30,
      "opacity": 100,
      "verticalAlign": "top",
      "updated": 1789386246190,
      "locked": false,
      "text": "Manual knowledge updates",
      "version": 3,
      "autoResize": true,
      "type": "text",
      "backgroundColor": "transparent",
      "index": "a1",
      "roundness": null,
      "containerId": null,
      "customData": {
        "codex": {
          "semanticId": "fireworks_title",
          "layoutRole": "section",
          "batchId": "nora_ingestion",
          "motion": false,
          "createdBy": "codex",
          "role": "title"
        }
      },
      "originalText": "Manual knowledge updates",
      "height": 37.5,
      "link": null,
      "strokeColor": "#0f172a",
      "fillStyle": "solid",
      "groupIds": [],
      "versionNonce": 1643127257,
      "textAlign": "left",
      "fontFamily": 5,
      "lineHeight": 1.25,
      "frameId": null,
      "boundElements": [],
      "x": 48,
      "angle": 0,
      "y": 28,
      "width": 527
    },
    {
      "seed": 860828781,
      "strokeStyle": "solid",
      "id": "4ccae40d",
      "strokeWidth": 1.5,
      "roughness": 0.2,
      "isDeleted": false,
      "fontSize": 18,
      "opacity": 100,
      "verticalAlign": "top",
      "updated": 1789386246327,
      "locked": false,
      "text": "An operator starts this workflow; user questions never trigger it.",
      "version": 3,
      "autoResize": true,
      "type": "text",
      "backgroundColor": "transparent",
      "index": "a2",
      "roundness": null,
      "containerId": null,
      "customData": {
        "codex": {
          "semanticId": "fireworks_subtitle",
          "layoutRole": "section",
          "batchId": "nora_ingestion",
          "motion": false,
          "createdBy": "codex",
          "role": "subtitle"
        }
      },
      "originalText": "An operator starts this workflow; user questions never trigger it.",
      "height": 22.5,
      "link": null,
      "strokeColor": "#64748b",
      "fillStyle": "solid",
      "groupIds": [],
      "versionNonce": 1923340882,
      "textAlign": "left",
      "fontFamily": 5,
      "lineHeight": 1.25,
      "frameId": null,
      "boundElements": [],
      "x": 48,
      "angle": 0,
      "y": 72,
      "width": 864
    },
    {
      "seed": 1404982499,
      "strokeStyle": "solid",
      "id": "fw_nora_ingestion_arrow_extract",
      "strokeWidth": 2,
      "roughness": 0.8,
      "isDeleted": false,
      "startBinding": null,
      "endArrowhead": "arrow",
      "opacity": 100,
      "updated": 1789385858197,
      "locked": false,
      "points": [
        [
          0,
          0
        ],
        [
          50,
          0
        ]
      ],
      "version": 2,
      "elbowed": false,
      "type": "arrow",
      "backgroundColor": "transparent",
      "index": "a3",
      "roundness": null,
      "lastCommittedPoint": null,
      "customData": {
        "codex": {
          "semanticId": "fireworks_arrow_extract",
          "motion": {
            "effect": "flow-dot",
            "journeyId": "fireworks-read",
            "enabled": true,
            "priority": 100
          },
          "batchId": "nora_ingestion",
          "createdBy": "codex",
          "role": "fireworks-arrow-read"
        }
      },
      "height": 0,
      "link": null,
      "startArrowhead": null,
      "strokeColor": "#0891b2",
      "fillStyle": "solid",
      "groupIds": [],
      "endBinding": null,
      "versionNonce": 46368963,
      "frameId": null,
      "boundElements": [],
      "x": 327.5,
      "angle": 0,
      "y": 228,
      "width": 50
    },
    {
      "seed": 229121741,
      "strokeStyle": "dashed",
      "id": "fw_nora_ingestion_arrow_prepare_text",
      "strokeWidth": 2,
      "roughness": 0.8,
      "isDeleted": false,
      "startBinding": null,
      "endArrowhead": "arrow",
      "opacity": 100,
      "updated": 1789385858197,
      "locked": false,
      "points": [
        [
          0,
          0
        ],
        [
          40,
          0
        ]
      ],
      "version": 2,
      "elbowed": false,
      "type": "arrow",
      "backgroundColor": "transparent",
      "index": "a4",
      "roundness": null,
      "lastCommittedPoint": null,
      "customData": {
        "codex": {
          "semanticId": "fireworks_arrow_prepare_text",
          "motion": {
            "effect": "flow-dot",
            "journeyId": "fireworks-write",
            "enabled": true,
            "priority": 99
          },
          "batchId": "nora_ingestion",
          "createdBy": "codex",
          "role": "fireworks-arrow-write"
        }
      },
      "height": 0,
      "link": null,
      "startArrowhead": null,
      "strokeColor": "#0f766e",
      "fillStyle": "solid",
      "groupIds": [],
      "endBinding": null,
      "versionNonce": 598251757,
      "frameId": null,
      "boundElements": [],
      "x": 667.5,
      "angle": 0,
      "y": 228,
      "width": 40
    },
    {
      "seed": 394772611,
      "strokeStyle": "solid",
      "id": "fw_nora_ingestion_arrow_encode",
      "strokeWidth": 2,
      "roughness": 0.8,
      "isDeleted": false,
      "startBinding": null,
      "endArrowhead": "arrow",
      "opacity": 100,
      "updated": 1789385858197,
      "locked": false,
      "points": [
        [
          0,
          0
        ],
        [
          0,
          133
        ]
      ],
      "version": 2,
      "elbowed": false,
      "type": "arrow",
      "backgroundColor": "transparent",
      "index": "a5",
      "roundness": null,
      "lastCommittedPoint": null,
      "customData": {
        "codex": {
          "semanticId": "fireworks_arrow_encode",
          "motion": {
            "effect": "flow-dot",
            "journeyId": "fireworks-read",
            "enabled": true,
            "priority": 98
          },
          "batchId": "nora_ingestion",
          "createdBy": "codex",
          "role": "fireworks-arrow-read"
        }
      },
      "height": 133,
      "link": null,
      "startArrowhead": null,
      "strokeColor": "#0891b2",
      "fillStyle": "solid",
      "groupIds": [],
      "endBinding": null,
      "versionNonce": 997947491,
      "frameId": null,
      "boundElements": [],
      "x": 860,
      "angle": 0,
      "y": 296.5,
      "width": 0
    },
    {
      "isDeleted": false,
      "locked": false,
      "strokeColor": "#64748b",
      "link": null,
      "roughness": 0.8,
      "groupIds": [
        "fw_nora_ingestion_group_originals"
      ],
      "index": "a6",
      "backgroundColor": "#ffffff",
      "angle": 0,
      "customData": {
        "codex": {
          "semanticId": "fireworks_node_originals",
          "layoutRole": "container",
          "batchId": "nora_ingestion",
          "motion": {
            "pulse": true,
            "effect": "pulse",
            "priority": 1
          },
          "createdBy": "codex",
          "role": "fireworks-rect"
        }
      },
      "fillStyle": "solid",
      "strokeWidth": 1.7,
      "version": 2,
      "roundness": null,
      "type": "rectangle",
      "updated": 1789385858197,
      "id": "fw_nora_ingestion_node_originals",
      "x": 48,
      "seed": 1650636835,
      "boundElements": [],
      "y": 160,
      "opacity": 100,
      "height": 136,
      "width": 279,
      "frameId": null,
      "strokeStyle": "solid",
      "versionNonce": 1658090499
    },
    {
      "seed": 1952354189,
      "strokeStyle": "solid",
      "id": "afc1dff9",
      "strokeWidth": 1.5,
      "roughness": 0.2,
      "isDeleted": false,
      "fontSize": 18,
      "opacity": 100,
      "verticalAlign": "top",
      "updated": 1789386246394,
      "locked": false,
      "text": "Originals",
      "version": 3,
      "autoResize": true,
      "type": "text",
      "backgroundColor": "transparent",
      "index": "a7",
      "roundness": null,
      "containerId": null,
      "customData": {
        "codex": {
          "semanticId": "fireworks_node_originals_label",
          "layoutRole": "section",
          "batchId": "nora_ingestion",
          "motion": false,
          "createdBy": "codex",
          "role": "fireworks-node-label"
        }
      },
      "originalText": "Originals",
      "height": 22.5,
      "link": null,
      "strokeColor": "#0f172a",
      "fillStyle": "solid",
      "groupIds": [
        "fw_nora_ingestion_group_originals"
      ],
      "versionNonce": 412469880,
      "textAlign": "left",
      "fontFamily": 5,
      "lineHeight": 1.25,
      "frameId": null,
      "boundElements": [],
      "x": 72,
      "angle": 0,
      "y": 184,
      "width": 125
    },
    {
      "seed": 1916648387,
      "strokeStyle": "solid",
      "id": "ef6bfb55",
      "strokeWidth": 1.5,
      "roughness": 0.2,
      "isDeleted": false,
      "fontSize": 16,
      "opacity": 100,
      "verticalAlign": "top",
      "updated": 1789386246462,
      "locked": false,
      "text": "Selected documents",
      "version": 3,
      "autoResize": true,
      "type": "text",
      "backgroundColor": "transparent",
      "index": "a8",
      "roundness": null,
      "containerId": null,
      "customData": {
        "codex": {
          "semanticId": "fireworks_node_originals_sublabel",
          "layoutRole": "section",
          "batchId": "nora_ingestion",
          "motion": false,
          "createdBy": "codex",
          "role": "fireworks-node-sublabel"
        }
      },
      "originalText": "Selected documents",
      "height": 20,
      "link": null,
      "strokeColor": "#475569",
      "fillStyle": "solid",
      "groupIds": [
        "fw_nora_ingestion_group_originals"
      ],
      "versionNonce": 134316642,
      "textAlign": "left",
      "fontFamily": 5,
      "lineHeight": 1.25,
      "frameId": null,
      "boundElements": [],
      "x": 72,
      "angle": 0,
      "y": 258,
      "width": 216
    },
    {
      "isDeleted": false,
      "locked": false,
      "strokeColor": "#64748b",
      "link": null,
      "roughness": 0.8,
      "groupIds": [
        "fw_nora_ingestion_group_prepare"
      ],
      "index": "a9",
      "backgroundColor": "#ffffff",
      "angle": 0,
      "customData": {
        "codex": {
          "semanticId": "fireworks_node_prepare",
          "layoutRole": "container",
          "batchId": "nora_ingestion",
          "motion": {
            "pulse": true,
            "effect": "pulse",
            "priority": 1
          },
          "createdBy": "codex",
          "role": "fireworks-rect"
        }
      },
      "fillStyle": "solid",
      "strokeWidth": 1.7,
      "version": 2,
      "roundness": null,
      "type": "rectangle",
      "updated": 1789385858197,
      "id": "fw_nora_ingestion_node_prepare",
      "x": 378,
      "seed": 643765741,
      "boundElements": [],
      "y": 160,
      "opacity": 100,
      "height": 136,
      "width": 289,
      "frameId": null,
      "strokeStyle": "solid",
      "versionNonce": 1665942541
    },
    {
      "seed": 1127697251,
      "strokeStyle": "solid",
      "id": "f5b36649",
      "strokeWidth": 1.5,
      "roughness": 0.2,
      "isDeleted": false,
      "fontSize": 18,
      "opacity": 100,
      "verticalAlign": "top",
      "updated": 1789386246530,
      "locked": false,
      "text": "Prepare",
      "version": 3,
      "autoResize": true,
      "type": "text",
      "backgroundColor": "transparent",
      "index": "aa",
      "roundness": null,
      "containerId": null,
      "customData": {
        "codex": {
          "semanticId": "fireworks_node_prepare_label",
          "layoutRole": "section",
          "batchId": "nora_ingestion",
          "motion": false,
          "createdBy": "codex",
          "role": "fireworks-node-label"
        }
      },
      "originalText": "Prepare",
      "height": 22.5,
      "link": null,
      "strokeColor": "#0f172a",
      "fillStyle": "solid",
      "groupIds": [
        "fw_nora_ingestion_group_prepare"
      ],
      "versionNonce": 1353186735,
      "textAlign": "left",
      "fontFamily": 5,
      "lineHeight": 1.25,
      "frameId": null,
      "boundElements": [],
      "x": 402,
      "angle": 0,
      "y": 184,
      "width": 99
    },
    {
      "seed": 658493517,
      "strokeStyle": "solid",
      "id": "248927d2",
      "strokeWidth": 1.5,
      "roughness": 0.2,
      "isDeleted": false,
      "fontSize": 16,
      "opacity": 100,
      "verticalAlign": "top",
      "updated": 1789386246598,
      "locked": false,
      "text": "Extract + normalize",
      "version": 3,
      "autoResize": true,
      "type": "text",
      "backgroundColor": "transparent",
      "index": "ab",
      "roundness": null,
      "containerId": null,
      "customData": {
        "codex": {
          "semanticId": "fireworks_node_prepare_sublabel",
          "layoutRole": "section",
          "batchId": "nora_ingestion",
          "motion": false,
          "createdBy": "codex",
          "role": "fireworks-node-sublabel"
        }
      },
      "originalText": "Extract + normalize",
      "height": 20,
      "link": null,
      "strokeColor": "#475569",
      "fillStyle": "solid",
      "groupIds": [
        "fw_nora_ingestion_group_prepare"
      ],
      "versionNonce": 1239194426,
      "textAlign": "left",
      "fontFamily": 5,
      "lineHeight": 1.25,
      "frameId": null,
      "boundElements": [],
      "x": 402,
      "angle": 0,
      "y": 258,
      "width": 227
    },
    {
      "isDeleted": false,
      "locked": false,
      "strokeColor": "#64748b",
      "link": null,
      "roughness": 0.8,
      "groupIds": [
        "fw_nora_ingestion_group_text"
      ],
      "index": "ac",
      "backgroundColor": "#ffffff",
      "angle": 0,
      "customData": {
        "codex": {
          "semanticId": "fireworks_node_text",
          "layoutRole": "container",
          "batchId": "nora_ingestion",
          "motion": {
            "pulse": true,
            "effect": "pulse",
            "priority": 1
          },
          "createdBy": "codex",
          "role": "fireworks-rect"
        }
      },
      "fillStyle": "solid",
      "strokeWidth": 1.7,
      "version": 2,
      "roundness": null,
      "type": "rectangle",
      "updated": 1789385858197,
      "id": "fw_nora_ingestion_node_text",
      "x": 708,
      "seed": 1235085059,
      "boundElements": [],
      "y": 160,
      "opacity": 100,
      "height": 136,
      "width": 303,
      "frameId": null,
      "strokeStyle": "solid",
      "versionNonce": 394702563
    },
    {
      "seed": 349847213,
      "strokeStyle": "solid",
      "id": "f9501d46",
      "strokeWidth": 1.5,
      "roughness": 0.2,
      "isDeleted": false,
      "fontSize": 18,
      "opacity": 100,
      "verticalAlign": "top",
      "updated": 1789386246674,
      "locked": false,
      "text": "Prepared text",
      "version": 3,
      "autoResize": true,
      "type": "text",
      "backgroundColor": "transparent",
      "index": "ad",
      "roundness": null,
      "containerId": null,
      "customData": {
        "codex": {
          "semanticId": "fireworks_node_text_label",
          "layoutRole": "section",
          "batchId": "nora_ingestion",
          "motion": false,
          "createdBy": "codex",
          "role": "fireworks-node-label"
        }
      },
      "originalText": "Prepared text",
      "height": 22.5,
      "link": null,
      "strokeColor": "#0f172a",
      "fillStyle": "solid",
      "groupIds": [
        "fw_nora_ingestion_group_text"
      ],
      "versionNonce": 155705483,
      "textAlign": "left",
      "fontFamily": 5,
      "lineHeight": 1.25,
      "frameId": null,
      "boundElements": [],
      "x": 732,
      "angle": 0,
      "y": 184,
      "width": 177
    },
    {
      "seed": 1810894499,
      "strokeStyle": "solid",
      "id": "54082fca",
      "strokeWidth": 1.5,
      "roughness": 0.2,
      "isDeleted": false,
      "fontSize": 16,
      "opacity": 100,
      "verticalAlign": "top",
      "updated": 1789386246824,
      "locked": false,
      "text": "GCS or local files",
      "version": 3,
      "autoResize": true,
      "type": "text",
      "backgroundColor": "transparent",
      "index": "ae",
      "roundness": null,
      "containerId": null,
      "customData": {
        "codex": {
          "semanticId": "fireworks_node_text_sublabel",
          "layoutRole": "section",
          "batchId": "nora_ingestion",
          "motion": false,
          "createdBy": "codex",
          "role": "fireworks-node-sublabel"
        }
      },
      "originalText": "GCS or local files",
      "height": 20,
      "link": null,
      "strokeColor": "#475569",
      "fillStyle": "solid",
      "groupIds": [
        "fw_nora_ingestion_group_text"
      ],
      "versionNonce": 714227638,
      "textAlign": "left",
      "fontFamily": 5,
      "lineHeight": 1.25,
      "frameId": null,
      "boundElements": [],
      "x": 732,
      "angle": 0,
      "y": 258,
      "width": 216
    },
    {
      "isDeleted": false,
      "locked": false,
      "strokeColor": "#64748b",
      "link": null,
      "roughness": 0.8,
      "groupIds": [
        "fw_nora_ingestion_group_index"
      ],
      "index": "af",
      "backgroundColor": "#ffffff",
      "angle": 0,
      "customData": {
        "codex": {
          "semanticId": "fireworks_node_index",
          "layoutRole": "container",
          "batchId": "nora_ingestion",
          "motion": {
            "pulse": true,
            "effect": "pulse",
            "priority": 1
          },
          "createdBy": "codex",
          "role": "fireworks-rect"
        }
      },
      "fillStyle": "solid",
      "strokeWidth": 1.7,
      "version": 2,
      "roundness": null,
      "type": "rectangle",
      "updated": 1789385858197,
      "id": "fw_nora_ingestion_node_index",
      "x": 378,
      "seed": 366469389,
      "boundElements": [],
      "y": 430,
      "opacity": 100,
      "height": 136,
      "width": 268,
      "frameId": null,
      "strokeStyle": "solid",
      "versionNonce": 150881069
    },
    {
      "seed": 1021067843,
      "strokeStyle": "solid",
      "id": "53e85561",
      "strokeWidth": 1.5,
      "roughness": 0.2,
      "isDeleted": false,
      "fontSize": 18,
      "opacity": 100,
      "verticalAlign": "top",
      "updated": 1789386246897,
      "locked": false,
      "text": "Qdrant",
      "version": 3,
      "autoResize": true,
      "type": "text",
      "backgroundColor": "transparent",
      "index": "ag",
      "roundness": null,
      "containerId": null,
      "customData": {
        "codex": {
          "semanticId": "fireworks_node_index_label",
          "layoutRole": "section",
          "batchId": "nora_ingestion",
          "motion": false,
          "createdBy": "codex",
          "role": "fireworks-node-label"
        }
      },
      "originalText": "Qdrant",
      "height": 22.5,
      "link": null,
      "strokeColor": "#0f172a",
      "fillStyle": "solid",
      "groupIds": [
        "fw_nora_ingestion_group_index"
      ],
      "versionNonce": 1057632164,
      "textAlign": "left",
      "fontFamily": 5,
      "lineHeight": 1.25,
      "frameId": null,
      "boundElements": [],
      "x": 402,
      "angle": 0,
      "y": 454,
      "width": 86
    },
    {
      "seed": 1068644205,
      "strokeStyle": "solid",
      "id": "16d3a26c",
      "strokeWidth": 1.5,
      "roughness": 0.2,
      "isDeleted": false,
      "fontSize": 16,
      "opacity": 100,
      "verticalAlign": "top",
      "updated": 1789386246976,
      "locked": false,
      "text": "Rebuildable index",
      "version": 3,
      "autoResize": true,
      "type": "text",
      "backgroundColor": "transparent",
      "index": "ah",
      "roundness": null,
      "containerId": null,
      "customData": {
        "codex": {
          "semanticId": "fireworks_node_index_sublabel",
          "layoutRole": "section",
          "batchId": "nora_ingestion",
          "motion": false,
          "createdBy": "codex",
          "role": "fireworks-node-sublabel"
        }
      },
      "originalText": "Rebuildable index",
      "height": 20,
      "link": null,
      "strokeColor": "#475569",
      "fillStyle": "solid",
      "groupIds": [
        "fw_nora_ingestion_group_index"
      ],
      "versionNonce": 861920047,
      "textAlign": "left",
      "fontFamily": 5,
      "lineHeight": 1.25,
      "frameId": null,
      "boundElements": [],
      "x": 402,
      "angle": 0,
      "y": 528,
      "width": 204
    },
    {
      "isDeleted": false,
      "locked": false,
      "strokeColor": "#64748b",
      "link": null,
      "roughness": 0.8,
      "groupIds": [
        "fw_nora_ingestion_group_embed"
      ],
      "index": "ai",
      "backgroundColor": "#ffffff",
      "angle": 0,
      "customData": {
        "codex": {
          "semanticId": "fireworks_node_embed",
          "layoutRole": "container",
          "batchId": "nora_ingestion",
          "motion": {
            "pulse": true,
            "effect": "pulse",
            "priority": 1
          },
          "createdBy": "codex",
          "role": "fireworks-rect"
        }
      },
      "fillStyle": "solid",
      "strokeWidth": 1.7,
      "version": 2,
      "roundness": null,
      "type": "rectangle",
      "updated": 1789385858197,
      "id": "fw_nora_ingestion_node_embed",
      "x": 708,
      "seed": 1967194595,
      "boundElements": [],
      "y": 430,
      "opacity": 100,
      "height": 136,
      "width": 303,
      "frameId": null,
      "strokeStyle": "solid",
      "versionNonce": 116151747
    },
    {
      "seed": 1018347981,
      "strokeStyle": "solid",
      "id": "4cee4136",
      "strokeWidth": 1.5,
      "roughness": 0.2,
      "isDeleted": false,
      "fontSize": 18,
      "opacity": 100,
      "verticalAlign": "top",
      "updated": 1789386247076,
      "locked": false,
      "text": "Chunk + embed",
      "version": 3,
      "autoResize": true,
      "type": "text",
      "backgroundColor": "transparent",
      "index": "aj",
      "roundness": null,
      "containerId": null,
      "customData": {
        "codex": {
          "semanticId": "fireworks_node_embed_label",
          "layoutRole": "section",
          "batchId": "nora_ingestion",
          "motion": false,
          "createdBy": "codex",
          "role": "fireworks-node-label"
        }
      },
      "originalText": "Chunk + embed",
      "height": 22.5,
      "link": null,
      "strokeColor": "#0f172a",
      "fillStyle": "solid",
      "groupIds": [
        "fw_nora_ingestion_group_embed"
      ],
      "versionNonce": 22021514,
      "textAlign": "left",
      "fontFamily": 5,
      "lineHeight": 1.25,
      "frameId": null,
      "boundElements": [],
      "x": 732,
      "angle": 0,
      "y": 454,
      "width": 177
    },
    {
      "seed": 774688131,
      "strokeStyle": "solid",
      "id": "a4335385",
      "strokeWidth": 1.5,
      "roughness": 0.2,
      "isDeleted": false,
      "fontSize": 16,
      "opacity": 100,
      "verticalAlign": "top",
      "updated": 1789386247164,
      "locked": false,
      "text": "BGE embeddings",
      "version": 3,
      "autoResize": true,
      "type": "text",
      "backgroundColor": "transparent",
      "index": "ak",
      "roundness": null,
      "containerId": null,
      "customData": {
        "codex": {
          "semanticId": "fireworks_node_embed_sublabel",
          "layoutRole": "section",
          "batchId": "nora_ingestion",
          "motion": false,
          "createdBy": "codex",
          "role": "fireworks-node-sublabel"
        }
      },
      "originalText": "BGE embeddings",
      "height": 20,
      "link": null,
      "strokeColor": "#475569",
      "fillStyle": "solid",
      "groupIds": [
        "fw_nora_ingestion_group_embed"
      ],
      "versionNonce": 1397835939,
      "textAlign": "left",
      "fontFamily": 5,
      "lineHeight": 1.25,
      "frameId": null,
      "boundElements": [],
      "x": 732,
      "angle": 0,
      "y": 528,
      "width": 170
    },
    {
      "seed": 723467629,
      "strokeStyle": "solid",
      "id": "nora_import_arrow",
      "strokeWidth": 2,
      "roughness": 0,
      "isDeleted": false,
      "startBinding": null,
      "endArrowhead": "arrow",
      "opacity": 100,
      "updated": 1789385906359,
      "locked": false,
      "points": [
        [
          0,
          0
        ],
        [
          59,
          0
        ]
      ],
      "version": 3,
      "elbowed": false,
      "type": "arrow",
      "backgroundColor": "transparent",
      "index": "al",
      "roundness": null,
      "lastCommittedPoint": null,
      "customData": {
        "codex": {
          "semanticId": "ingestion_index_write",
          "batchId": "nora_import_arrow",
          "createdBy": "codex",
          "role": "arrow"
        }
      },
      "height": 0,
      "link": null,
      "startArrowhead": null,
      "strokeColor": "#0f766e",
      "fillStyle": "solid",
      "groupIds": [],
      "endBinding": null,
      "versionNonce": 464092627,
      "frameId": null,
      "boundElements": [],
      "x": 647.5,
      "angle": 3.141592653589793,
      "y": 498,
      "width": 59
    }
  ],
  "source": "codex-excalidraw-canvas",
  "type": "excalidraw",
  "files": {},
  "version": 2,
  "appState": {
    "gridStep": 5,
    "currentItemBackgroundColor": "transparent",
    "currentItemArrowType": "sharp",
    "currentItemStrokeColor": "#1e1e1e",
    "currentItemStrokeWidthKey": "medium",
    "objectsSnapModeEnabled": false,
    "currentItemStrokeStyle": "solid",
    "currentItemEndArrowhead": "arrow",
    "currentItemRoundness": "round",
    "zenModeEnabled": false,
    "stats": {
      "panels": 3,
      "open": false
    },
    "currentItemFontSize": 20,
    "gridSize": 20,
    "currentItemTextAlign": "left",
    "viewModeEnabled": false,
    "isMidpointSnappingEnabled": true,
    "bindingPreference": "enabled",
    "viewBackgroundColor": "#fbfbfa",
    "boxSelectionMode": "contain",
    "currentItemOpacity": 100,
    "preferredSelectionTool": {
      "type": "selection",
      "initialized": true
    },
    "currentItemStartArrowhead": null,
    "currentItemStrokeVariability": "constant",
    "currentItemRoughness": 1,
    "name": "manual-ingestion",
    "gridModeEnabled": false,
    "currentItemFontFamily": 5,
    "currentItemFillStyle": "solid"
  }
}
```
%%
