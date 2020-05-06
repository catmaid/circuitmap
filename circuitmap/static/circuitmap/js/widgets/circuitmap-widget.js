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
        controls.classList.add('vertical-settings');

        let fetchSynHeader = controls.appendChild(document.createElement('h3'));
        fetchSynHeader.appendChild(document.createTextNode('Fetch synapses for active skeleton'));

        let fetchCutoffSetting = CATMAID.DOM.createNumericInputSetting('Max dist. from sekelton (nm)',
            this.distance_threshold, 50, "If the distance between the skeleton and a candidate synapse is larger, the synapse is ignored.",
            e => this.distance_threshold = parseInt(e.target.value,10));
        fetchCutoffSetting.find('input').attr('id', `distance_threshold${this.widgetID}`);
        $(controls).append(fetchCutoffSetting);

        var fetch = document.createElement('input');
        fetch.setAttribute("type", "button");
        fetch.setAttribute("value", "Fetch synapses for active neuron");
        fetch.onclick = this.fetch.bind(this);
        controls.appendChild(fetch);

        var optionFields = document.createElement('div');
        optionFields.innerHTML = `
        <table cellpadding="0" cellspacing="0" border="0"
              id="circuitmap_flow2_option_fields${this.widgetID}">
          <tr>
            <td><h3>Fetch autoseg skeleton and synapses at location</h3></td>
            <td></td>
          </tr>
        </table>
        `;
        controls.appendChild(optionFields);

        // Reference lines
        let refLines = CATMAID.DOM.createCheckboxSetting("Display reference lines",
            CATMAID.StackViewer.Settings.session.display_stack_reference_lines,
            "Show crossing lines that point to where segments are looked up", e => {
              project.getStackViewers().forEach(s => s.showReferenceLines(e.target.checked));
            });
        refLines.css('display', 'block');
        $(controls).append(refLines);

        // Upstream autoseg partners
        let fetchUpstreamThresholdInput = document.createElement('input');
        fetchUpstreamThresholdInput.setAttribute('type', 'number');
        fetchUpstreamThresholdInput.setAttribute('min', '0');
        fetchUpstreamThresholdInput.setAttribute('style', 'width: 5em');
        fetchUpstreamThresholdInput.setAttribute('value', this.upstream_syn_count);
        fetchUpstreamThresholdInput.addEventListener('open', e => {
          this.upstream_syn_count = parseInt(e.target.value, 10);
        });
        fetchUpstreamThresholdInput.setAttribute('id', `upstream_syn_count${this.widgetID}`);
        fetchUpstreamThresholdInput.disabled = !this.fetch_upstream_skeletons;

        let fetchUpstreamPartners = CATMAID.DOM.createCheckboxSetting("Fetch upstream autoseg partner skeletons connected via at least ",
            this.fetch_upstream_skeletons,
            "Import any upstream partner autoseg skeleton that is connected though a minimum of N synapses.", e => {
              this.fetch_upstream_skeletons = e.target.checked;
              fetchUpstreamThresholdInput.disabled = !e.target.checked;
            });
        fetchUpstreamPartners.css('display', 'block');
        $(controls).append(fetchUpstreamPartners);
        let fetchUpstreamPartnerLabel = fetchUpstreamPartners.find('label');
        fetchUpstreamPartnerLabel.append(fetchUpstreamThresholdInput);
        fetchUpstreamPartnerLabel.append('synapses');

        // Downstream autoseg partners
        let fetchDownstreamThresholdInput = document.createElement('input');
        fetchDownstreamThresholdInput.setAttribute('type', 'number');
        fetchDownstreamThresholdInput.setAttribute('min', '0');
        fetchDownstreamThresholdInput.setAttribute('style', 'width: 5em');
        fetchDownstreamThresholdInput.setAttribute('value', this.downstream_syn_count);
        fetchDownstreamThresholdInput.addEventListener('open', e => {
          this.downstream_syn_count = parseInt(e.target.value, 10);
        });
        fetchDownstreamThresholdInput.setAttribute('id', `downstream_syn_count${this.widgetID}`);
        fetchDownstreamThresholdInput.disabled = !this.fetch_downstream_skeletons;

        let fetchDownstreamPartners = CATMAID.DOM.createCheckboxSetting("Fetch downstream autoseg partner skeletons connected via at least ",
            this.fetch_downstream_skeletons,
            "Import any downstream partner autoseg skeleton that is connected through a minimum of N synapses.", e => {
              this.fetch_downstream_skeletons = e.target.checked;
              fetchDownstreamThresholdInput.disabled = !e.target.checked;
            });
        fetchDownstreamPartners.css('display', 'block');
        $(controls).append(fetchDownstreamPartners);

        let fetchDownstreamPartnerLabel = fetchDownstreamPartners.find('label');
        fetchDownstreamPartnerLabel.append(fetchDownstreamThresholdInput);
        fetchDownstreamPartnerLabel.append('synapses');

        var fetch = document.createElement('input');
        fetch.classList.add('clear');
        fetch.setAttribute("type", "button");
        fetch.setAttribute("value", "Fetch autoseg skeleton and synapses at location");
        fetch.onclick = this.fetch_location.bind(this);
        controls.appendChild(fetch);
      },
      contentID: this.idPrefix + 'content',
      createContent: function(container) {
        this.content = container;
        this.updateMessage();
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
          this.content.dataset.msg = `Fetch all synapses for the active skeleton with ID #${skeletonId} or find a segmentation fragment plus its synapses for the current location.`;
        } else {
          this.content.dataset.msg = "Select a skeleton to fetch synapses for or fetch a segmentation fragment plus its synapses for the current location.";
        }
      } else {
        this.content.dataset.msg = "Select a skeleton to fetch synapses for or fetch a segmentation fragment plus its synapses for the current location.";
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
      'source_hash': this.sourceHash,
    };

    this.updateMessage(`Fetching synapses for skeleton #${activeSkeletonId}`);
    CATMAID.fetch('ext/circuitmap/' + project.id + '/synapses/fetch', 'POST', query_data)
      .then(e => {
        CATMAID.msg("Success", "Import process started ...");
      })
      .catch(e => {
        this.updateMessage(`An error occured while fetching synapses for skeleton #{activeSkeletonId}: ${e}`);
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
      'y':  stackViewer.y,
      'z':  stackViewer.z,
      'fetch_upstream': this.fetch_upstream_skeletons,
      'fetch_downstream': this.fetch_downstream_skeletons,
      'distance_threshold': this.distance_threshold,
      'upstream_syn_count': this.upstream_syn_count,
      'downstream_syn_count': this.downstream_syn_count,
      'active_skeleton': -1,
      'source_hash': this.sourceHash,
    };

    this.updateMessage(`Fetching segment and synapses for stack location (${stackViewer.x}, ${stackViewer.y}, ${stackViewer.z})`);
    CATMAID.fetch('ext/circuitmap/' + project.id + '/synapses/fetch', 'POST', query_data)
      .then(function(e) {
        CATMAID.msg("Success", "Import process started ...");
      })
      .catch(e => {
        this.updateMessage(`An error occured while fetching segment and synapses for stack location (${stackViewer.x}, ${stackViewer.y}, ${stackViewer.z}): ${e.message}`);
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
        this.updateMessage(`Imported ${info.n_inserted_synapses} synapses and ${info.n_inserted_links} ` +
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
        this.updateMessage(`Imported ${info.n_upsteam_partners} partners and ${info.n_downstream_partners} ` +
            `for skeleton/segment ${info.segment_id}`);
      }
    } else {
      this.updateMessage(`Completed task of unnknown type: ${info.task}`);
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
    let widget = CircuitmapWidget.findWidgetWithSourceHash(info.source_hash);
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
