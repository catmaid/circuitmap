/* -*- mode: espresso; espresso-indent-level: 8; indent-tabs-mode: t -*- */
/* vim: set softtabstop=2 shiftwidth=2 tabstop=2 expandtab: */

(function(CATMAID) {

  "use strict";

  var CircuitmapWidget = function() {
    this.widgetID = this.registerInstance();
    this.idPrefix = `circuitmap-widget${this.widgetID}-`;
    // This random number is sent to the server along with requests to make it
    // easier to associate the result messages with individual widgets.
    this.sourceHash = `${Math.floor(Math.random() * Math.floor(2**16))}`;

    this.fetch_upstream_skeletons = false;
    this.fetch_downstream_skeletons = false;
    this.distance_threshold = 1000;
    this.upstream_syn_count = 5;
    this.downstream_syn_count = 5;
    this.content = undefined;
    this.autoSelectResultSkeleton = true;
    this.allowAutapses = false;
    this.importAnnotations = CATMAID.TracingTool.getDefaultImportAnnotations();
    this.importTags = CATMAID.TracingTool.getDefaultImportTags();

    let config = CATMAID.extensionConfig['circuitmap']
    this.sourceRemote = config ? config['seg_name'] : '';

    // The UI representation of past and current imports
    this.importTable = null;

    SkeletonAnnotations.on(SkeletonAnnotations.EVENT_ACTIVE_NODE_CHANGED,
        this.handleActiveNodeChange, this);
  };

  $.extend(CircuitmapWidget.prototype, new InstanceRegistry());

  CircuitmapWidget.prototype.getName = function() {
    return 'Circuitmap Widget ' + this.widgetID;
  };

  CircuitmapWidget.prototype.getWidgetConfiguration = function() {
    return {
      controlsID: this.idPrefix + 'controls',
      createControls: function(controls) {
        let activeSkeletonTab = 'Synapses for active skeleton';
        let locationTab = 'Synapses and segment for location';
        var tabs = CATMAID.DOM.addTabGroup(controls, this.widgetID,
            ['Main', activeSkeletonTab, locationTab]);

        let getAnnotationTitle = () => {
          let annotations = CATMAID.TracingTool.getEffectiveImportAnnotations(this.importAnnotations, this.sourceRemote);
          return `A set of annotation terms, separated by comma, that will be added to import skeletons as annotations. Every occurence of "{group}" will be replaced with your primary group (or your username, should now primary group be defined). Every occurence of "{source}" will be replaced with the handle of the import source (e.g. the server name).\n\nCurrent set of annotations: ${annotations}`;
        };

        let getTagTitle = () => {
          let tags = CATMAID.TracingTool.getEffectiveImportTags(this.importTags, this.sourceRemote);
          return `A set of tags, separated by comma, that will be added to imported synapses (connector nodes) as tags. Every occurence of "{group}" will be replaced with your primary group (or your username, should now primary group be defined). Every occurence of "{source}" will be replaced with the handle of the import source (e.g. the server name).\n\nCurrent set of tags: ${tags}`;
        };

        CATMAID.DOM.appendToTab(tabs['Main'], [
          {
            type: 'button',
            label: 'Refresh',
            title: 'Reload the import table',
            onclick: e => {
              this.refresh();
            }
          },
          {
            type: 'text',
            label: 'Import tags',
            title: getTagTitle(),
            value: this.importTags.join(', '),
            length: 15,
            onchange: e => {
              this.importTags = e.target.value.split(',').map(v => v.trim());
            }
          },
          {
            type: 'text',
            label: 'Import annotations',
            title: getAnnotationTitle(),
            value: this.importAnnotations.join(', '),
            length: 15,
            onchange: e => {
              this.importAnnotations = e.target.value.split(',').map(v => v.trim());
            }
          },
          {
            type: 'checkbox',
            label: 'Allow autapses',
            title: 'If enabled, imported synaptic links are allowed to form autapses.',
            onclick: e => {
              this.allowAutapses = e.target.checked;
            },
          },
        ]);

        controls.classList.add('vertical-settings');

        // Fetch active skeleton tab
        CATMAID.DOM.appendToTab(tabs[activeSkeletonTab], [
          {
            type: 'numeric',
            id: `distance_threshold${this.widgetID}`,
            label: 'Max dist. from skeleton (nm)',
            title: "If the distance between the skeleton and a candidate synapse is larger, the synapse is ignored.",
            value: this.distance_threshold,
            length: 5,
            min: 0,
            onchange: e => {
              this.distance_threshold = parentInt(e.target.value, 10);
            }
          },
          {
            type: 'button',
            label: 'Fetch synapses for active neuron',
            onclick: e => this.fetch(),
          },
        ]);

        // Fetch location tab
        CATMAID.DOM.appendToTab(tabs[locationTab], [
          {
            type: 'checkbox',
            label: 'Display reference lines',
            title: 'Show crossing lines that point to where segments are looked up',
            value: CATMAID.StackViewer.Settings.session.display_stack_reference_lines,
            onclick: e => {
              project.getStackViewers().forEach(s => s.showReferenceLines(e.target.checked));
            },
          },
          {
            type: 'checkbox',
            label: 'Fetch upstream autoseg partners linked via at least',
            value: this.fetch_upstream_skeletons,
            title: 'Import any upstream partner autoseg skeleton that is connected though a minimum of N synapses.',
            onclick: e => {
              this.fetch_upstream_skeletons = e.target.checked;
              let upstreamSynThresholdInput = document.querySelector(`#upstream_syn_count${this.widgetID}`);
              if (upstreamSynThresholdInput) {
                upstreamSynThresholdInput.disabled = !e.target.checked;
              }
            },
          },
          {
            type: 'numeric',
            label: '',
            postlabel: 'synapses',
            value: this.upstream_syn_count,
            length: 3,
            min: 0,
            id: `upstream_syn_count${this.widgetID}`,
            disabled: !this.fetch_upstream_skeletons,
            onchange: e => {
              this.upstream_syn_count = parseInt(e.target.value, 10);
            },
          },
          {
            type: 'checkbox',
            label: 'Fetch downstream autoseg partners linked via at least',
            value: this.fetch_downstream_skeletons,
            title: 'Import any downstream partner autoseg skeleton that is connected though a minimum of N synapses.',
            onclick: e => {
              this.fetch_downstream_skeletons = e.target.checked;
              let downstreamSynThresholdInput = document.querySelector(`#downstream_syn_count${this.widgetID}`);
              if (downstreamSynThresholdInput) {
                downstreamSynThresholdInput.disabled = !e.target.checked;
              }
            },
          },
          {
            type: 'numeric',
            label: '',
            postlabel: 'synapses',
            value: this.downstream_syn_count,
            length: 3,
            min: 0,
            id: `downstream_syn_count${this.widgetID}`,
            disabled: !this.fetch_downstream_skeletons,
            onchange: e => {
              this.downstream_syn_count = parseInt(e.target.value, 10);
            },
          },
          {
            type: 'button',
            label: 'Fetch autoseg skeleton and synapses at location',
            onclick: e => this.fetch_location(),
          },
        ]);

        $(controls).tabs();
      },
      contentID: this.idPrefix + 'content',
      createContent: function(container) {
        this.content = container;
        this.updateMessage();

        let importTable = container.appendChild(document.createElement('table'));
        this.importTable = $(importTable).DataTable({
          dom: "lrphtip",
          paging: true,
          order: [[0, 'desc']],
          autoWidth: false,
          lengthMenu: [CATMAID.pageLengthOptions, CATMAID.pageLengthLabels],
          ajax: (data, callback, settings) => {
            CATMAID.fetch(`/ext/circuitmap/${project.id}/imports/`)
              .then(importData => {
                let skeletonIds = importData.map(r => r.skeleton_id).filter(skid => skid !== -1);
                return CATMAID.NeuronNameService.getInstance().registerAllFromList(this, skeletonIds)
                  .then(() => importData);
              })
              .then(importData => callback({
                  draw: data.draw,
                  data: importData,
              }))
              .catch(CATMAID.handleError);
          },
          columns: [
            {
              title: 'ID',
              data: 'id',
            },
            {
              title: 'User',
              data: 'user_id',
              render: function(data, type, row, meta) {
                return CATMAID.User.safe_get(row.user_id).login;
              }
            },
            {
              title: 'Neuron',
              data: 'skeleton_id',
              render: function(data, type, row, meta) {
                let name = CATMAID.NeuronNameService.getInstance().getName(data);
                return '<a href="#" class="neuron-selection-link" data-role="select-skeleton">' +
                  (name ? name : "(not yet available)") + '</a>';
              }
            }, {
              title: "Status",
              data: "status",
              orderable: true,
              class: 'cm-center',
              render: function(data, type, row, meta) {
                let status = row.status_detail && row.status_detail.length > 0 ?
                    row.status_detail : 'No details availale';
                return `<span title="${status}">${data}</a>`;
              }
            }, {
              title: "Last update (UTC)",
              data: "edition_time",
              class: "cm-center",
              searchable: true,
              orderable: true,
              render: function(data, type, row, meta) {
                if (type === 'display') {
                  var date = CATMAID.tools.isoStringToDate(row.creation_time);
                  if (date) {
                    return CATMAID.tools.dateToString(date);
                  } else {
                    return "(parse error)";
                  }
                } else {
                  return data;
                }
              }
            }, {
              data: "runtime",
              title: "Runtime",
              orderable: true,
              class: 'cm-center',
              render: function(data, type, row, meta) {
                return data ? (Math.round(data) + 's') : 'N/A';
              },
            }, {
              data: "n_imported_links",
              title: "# New links",
              class: "cm-center",
              searchable: true,
              orderable: true,
            }, {
              data: "n_imported_connectors",
              title: "# New connectors",
              class: "cm-center",
              searchable: true,
              orderable: true,
            }, {
              data: "n_upstream_partners",
              title: "# New up. partners",
              class: "cm-center",
              searchable: true,
              orderable: true,
            }, {
              data: "n_downstream_partners",
              title: "# New down. partners",
              class: "cm-center",
              searchable: true,
              orderable: true,
            }, {
              data: "upstream_partner_syn_threshold",
              title: "Up. syn thrsh.",
              class: "cm-center",
              searchable: true,
              orderable: true,
              render: function(data, type, row, meta) {
                return data < 0 ? '-' : data;
              },
            }, {
              data: "downsteam_partner_syn_threshold",
              title: "Down. syn thrsh.",
              class: "cm-center",
              searchable: true,
              orderable: true,
              render: function(data, type, row, meta) {
                return data < 0 ? '-' : data;
              },
            }, {
              data: "distance_threshold",
              title: "Dist. thrsh..",
              class: "cm-center",
              searchable: true,
              orderable: true,
            }, {
              data: "with_autapses",
              title: "Autapses",
              class: "cm-center",
              searchable: true,
              orderable: true,
              render: function(data, type, row, meta) {
                return data ? "Yes" : "No";
              },
            },
          ],
          language: {
            emptyTable: 'No imports found',
          },
        }).on('click', 'a[data-role=select-skeleton]', e => {
          let data = this.importTable.row($(e.target).parents('tr')).data();
          if (data.skeleton_id === -1) {
            CATMAID.warn('Skeleton for segment not yet imported');
            return;
          }
          CATMAID.TracingTool.goToNearestInNeuronOrSkeleton('skeleton', data.skeleton_id);
        });
      },
      init: function() {
        var self = this;

        $('#fetch_upstream_skeleton' + self.widgetID).change(function() {
          self.fetch_upstream_skeleton = this.checked;
        });

        $('#fetch_downstream_skeleton' + self.widgetID).change(function() {
          self.fetch_downstream_skeleton = this.checked;
        });

        $('#distance_threshold' + self.widgetID).change(function() {
          self.distance_threshold = this.value;
        });

        $('#upstream_syn_count' + self.widgetID).change(function() {
          self.upstream_syn_count = this.value;
        });

        $('#downstream_syn_count' + self.widgetID).change(function() {
          self.downstream_syn_count = this.value;
        });

      },
      helpPath: 'circuit-map.html',
    };
  };

  CircuitmapWidget.prototype.updateMessage = function(newMsg=undefined) {
    if (!this.content) {
      return;
    }
    if (newMsg !== undefined) {
      this.msg = newMsg;
    }
    if (this.msg) {
      this.content.dataset.msg = this.msg;
    } else {
      let atn = SkeletonAnnotations.getActiveNodeId();
      if (atn) {
        let atnType = SkeletonAnnotations.getActiveNodeType();
        if (atnType === SkeletonAnnotations.TYPE_NODE) {
          let skeletonId = SkeletonAnnotations.getActiveSkeletonId();
          this.content.dataset.msg = `Fetch all synapses for the active skeleton with ID #${skeletonId} or find a segmentation fragment plus its synapses for the current location using the respective tab above.`;
        } else {
          this.content.dataset.msg = "Please select the active skeleton tab or the location tab to import synapses.";
        }
      } else {
          this.content.dataset.msg = "Please select a skeleton and use the active skeleton tab or use the location tab to import synapses.";
      }
    }
  };

  CircuitmapWidget.prototype.handleActiveNodeChange = function() {
    this.updateMessage();
  };

  CircuitmapWidget.prototype.fetch = function() {
    var stackViewer = project.focusedStackViewer;
    var stack = project.focusedStackViewer.primaryStack;
    let activeSkeletonId = SkeletonAnnotations.getActiveSkeletonId();

    var query_data = {
      'x': stackViewer.x,
      'y':  stackViewer.y,
      'z':  stackViewer.z,
      'fetch_upstream': this.fetch_upstream_skeletons,
      'fetch_downstream': this.fetch_downstream_skeletons,
      'distance_threshold': this.distance_threshold,
      'upstream_syn_count': this.upstream_syn_count,
      'downstream_syn_count': this.downstream_syn_count,
      'active_skeleton': activeSkeletonId,
      'request_id': this.sourceHash,
      'with_autapses': this.allowAutapses,
      'annotations': CATMAID.TracingTool.getEffectiveImportAnnotations(
          this.importAnnotations, this.sourceRemote),
      'tags': CATMAID.TracingTool.getEffectiveImportTags(
          this.importTags, this.sourceRemote),
    };

    this.updateMessage(`Fetching synapses for skeleton #${activeSkeletonId}`);
    CATMAID.fetch('ext/circuitmap/' + project.id + '/synapses/fetch', 'POST', query_data)
      .then(e => {
        CATMAID.msg("Success", "Import process started ...");
        this.refresh();
      })
      .catch(e => {
        this.updateMessage(`An error occured while fetching synapses for skeleton #{activeSkeletonId}: ${e}`);
        this.refresh();
        if (e.type !== 'CircuitMapError') {
          CATMAID.handleError(e);
        } else {
          CATMAID.warn(e.message);
        }
      });
  };

  CircuitmapWidget.prototype.fetch_location = function() {
    var stackViewer = project.focusedStackViewer;
    var stack = project.focusedStackViewer.primaryStack;

    var query_data = {
      'x': stackViewer.x,
      'y': stackViewer.y,
      'z': stackViewer.z,
      'fetch_upstream': this.fetch_upstream_skeletons,
      'fetch_downstream': this.fetch_downstream_skeletons,
      'distance_threshold': this.distance_threshold,
      'upstream_syn_count': this.upstream_syn_count,
      'downstream_syn_count': this.downstream_syn_count,
      'active_skeleton': -1,
      'request_id': this.sourceHash,
      'with_autapses': this.allowAutapses,
      'annotations': CATMAID.TracingTool.getEffectiveImportAnnotations(
          this.importAnnotations, this.sourceRemote),
      'tags': CATMAID.TracingTool.getEffectiveImportTags(
          this.importTags, this.sourceRemote),
    };

    this.updateMessage(`Fetching segment and synapses for stack location (${stackViewer.x}, ${stackViewer.y}, ${stackViewer.z})`);
    CATMAID.fetch('ext/circuitmap/' + project.id + '/synapses/fetch', 'POST', query_data)
      .then((e) => {
        CATMAID.msg("Success", "Import process started ...");
        this.refresh();
      })
      .catch(e => {
        this.updateMessage(`An error occured while fetching segment and synapses for stack location (${stackViewer.x}, ${stackViewer.y}, ${stackViewer.z}): ${e.message}`);
        this.refresh();
        if (e.type !== 'CircuitMapError') {
          CATMAID.handleError(e);
        } else {
          CATMAID.warn(e.message);
        }
      });

  };

  CircuitmapWidget.prototype.destroy = function() {
    this.unregisterInstance();
    CATMAID.NeuronNameService.getInstance().unregister(this);
    SkeletonAnnotations.off(SkeletonAnnotations.EVENT_ACTIVE_NODE_CHANGED,
        this.handleActiveNodeChange, this);
  };

  CircuitmapWidget.prototype.handleCircuitMapTaskUpdate = function(info) {
    CATMAID.msg(info.message ? info.message : 'Circuit Map computation done', `Task: ${info.task}`);
    if (!info) {
      throw new CATMAID.ValueError('Need circuit map update information');
    } else if (info.task === 'import-synapses') {
      if (info.error) {
        this.updateMessage(`Error during synapse import for skeleton ${info.skeleton_id}`);
      } else {
        this.updateMessage(`Imported ${info.n_inserted_synapses} synapses and ${info.n_inserted_links} links` +
            `for skeleton ${info.skeleton_id}`);
        if (info.hasOwnProperty('skeleton_id')) {
          // Issue a skeleton update event
          CATMAID.Skeletons.trigger(
              CATMAID.Skeletons.EVENT_SKELETON_CHANGED, info.skeleton_id);
        }
      }
    } else if (info.task === 'import-location') {
      let loc = `(${info.x}, ${info.y}, ${info.z})`;
      if (info.error) {
        this.updateMessage(`Error during segment and synapse look-up for location ${loc}: ${info.error}`);
      } else {
        this.updateMessage(`Imported skeleton/segment ${info.skeleton_id} at location ${loc} ` +
            `along with ${info.n_inserted_synapses} synapses and ${info.n_inserted_links} links`);
        // Since this skeleton wasn't there before, force update the view if no auto-selection is enabled.
        if (this.autoSelectResultSkeleton && info.skeleton_id) {
          CATMAID.TracingTool.goToNearestInNeuronOrSkeleton('skeleton', info.skeleton_id);
        } else {
          CATMAID.TracingTool.getTracingLayers().forEach(l => l.forceRedraw());
        }
      }
    } else if (info.task === 'import-partner-fragments') {
      if (info.error) {
        this.updateMessage(`Error during the import of partner fragments for segment ${info.segment_id}`);
      } else {
        this.updateMessage(`Imported ${info.n_upsteam_partners} partners and ${info.n_downstream_partners} links ` +
            `for skeleton/segment ${info.segment_id}`);
      }
    } else {
      this.updateMessage(`Completed task of unnknown type: ${info.task}`);
    }
    this.refresh();
  };

  CircuitmapWidget.prototype.refresh = function() {
    if (this.importTable) {
      this.importTable.ajax.reload();
    }
  };

  CircuitmapWidget.findWidgetWithSourceHash = function(sourceHash) {
    let map = CATMAID.WindowMaker.getOpenWidgetsOfType(CircuitmapWidget);
    for (let [win, widget] of map.entries()) {
      if (widget.sourceHash === sourceHash) {
        return widget;
      }
    }
  };

  CircuitmapWidget.handleCircuitMapTaskUpdate = function(client, info) {
    let widget = CircuitmapWidget.findWidgetWithSourceHash(info.request_id);
    if (widget) {
      widget.handleCircuitMapTaskUpdate(info);
    }
  };

  CATMAID.registerWidget({
    name: 'Circuit Map Widget',
    description: 'Widget associated with the circuitmap extension',
    key: 'circuitmap-widget',
    creator: CircuitmapWidget,
    websocketHandlers: {
      'circuitmap-update': CircuitmapWidget.handleCircuitMapTaskUpdate,
    },
  });

  // Inject Circuit Map into Tracing Tool
  CATMAID.TracingTool.actions.push(new CATMAID.Action({
    helpText: "Add synapses and fragments based on segmentation data",
    buttonID: "data_button_circuitmap",
    buttonName: 'circuitmap',
    run: function (e) {
      WindowMaker.create('circuitmap-widget');
      return true;
    }
  }));

})(CATMAID);
