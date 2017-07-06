/*
 * bootstrapAlert will add a Bootstrap alert message to the body of the current
 * page.
 *
 * @param message: Message to display
 * @param severit: One of 'danger', 'info', 'warning' or 'success'.
 * @param timeout: OPTIONAL. When given, time (in ms) before alert fades out
 *
 */

var timeoutHandleForBoostrapAlert = null;

function bootstrapAlert(message, severity, timeout){
  // Clear the previous alert - so they don't keep stacking on top of each other
  $('#bootstrap-alert').alert('close');

  // make timeout an optional parameter
  timeout = timeout || -1;

  severity = typeof severity !== 'undefined' ? severity : 'danger';
  $("#alert-message").remove();
  var alertDiv = $('<div>', { 'class': 'alert fade in alert-'+severity, 'role': 'alert', 'id': 'alert-message'});

  alertDiv.append('<a href="#" class="close" data-dismiss="alert">&times;</a>');
  alertDiv.append('<span class="glyphicon glyphicon-exclamation-sign" aria-hidden="true"></span>');

  // prepend a space to separate the message from the '!' icon
  alertDiv.append(' '+message);

  // prepend the "Need help" message
  if (severity == 'warning' || severity == 'danger'){
    alertDiv.append('<p style="text-align:center">Need help? Send us an <a href="mailto:qiita.help@gmail.com">email</a>.</p>');
  }

  $('#qiita-main').prepend(alertDiv);

  if(timeout > 0) {
   if (timeoutHandleForBoostrapAlert != null) {
     window.clearTimeout(timeoutHandleForBoostrapAlert);
   }
   timeoutHandleForBoostrapAlert = window.setTimeout(function() {
     $('#alert-message').alert('close');
     timeoutHandleForBoostrapAlert = null;
   }, timeout);
  }
}

function format_extra_info_processing_jobs ( data ) {
    // `data` is the original data object for the row
    // 0: blank +/- button
    // 1: heartbeat
    // 2: name
    // 3: status
    // 4: step
    // 5: id
    // 6: params
    // 7: processing_job_workflow_id

    let row = '<table cellpadding="5" cellspacing="0" border="0" style="padding-left:50px;">'+
                '<tr>'+
                    '<td><b>ID:</b></td>'+
                    '<td>'+ data[5] +'</td>'+
                '</tr>'+
                '<tr>'+
                    '<td colspan="2"><h5>Parameters:</h5>'+ data[6] +'</td>'+
                '</tr>';
    if (data[7] !== '' && data[3] === 'in_construction') {
      row += '<tr>'+
                '<td colspan="2">'+
                  '<button class="btn btn-danger btn-sm" onclick="remove_job(\''+ data[5] + "', '" + data[7] +'\');">'+
                  '<span class="glyphicon glyphicon-trash"></span></button>'+
                '</td>'
             '</tr>';
    }
    row += '</table>';

    return row
}


function show_hide(div) {
	$('#' + div).toggle();
}

function delete_analysis(aname, analysis_id) {
  if (confirm('Are you sure you want to delete analysis: ' + aname + '?')) {
    var form = $("<form>")
    .attr("action", window.location.href)
    .attr("method", "post")
    .append($("<input>")
    .attr("type", "hidden")
    .attr("name", "analysis_id")
    .attr("value", analysis_id))
    .append($("<input>")
    .attr("type", "hidden")
    .attr("name", "action")
    .attr("value", "delete_analysis"));
    $("body").append(form);
    form.submit();
  }
}

function show_hide_process_list() {
  if ($("#qiita-main").width() == $("#qiita-main").parent().width()) {
    // let's update the job list
    processing_jobs_vue.update_processing_job_data();
    $("#qiita-main").width("76%");
    $("#user-studies-table").width("76%");
    $("#studies-table").width("76%");
    $("#qiita-processing").width("24%");
    $("#qiita-processing").show();
  } else {
    $("#qiita-main").width("100%");
    $("#user-studies-table").width("100%");
    $("#studies-table").width("100%");
    $("#qiita-processing").width("0%");
    $("#qiita-processing").hide();
  }
}

/**
 * Draw the artifact + jobs processing graph
 *
 * Draws a vis.Network graph in the given target div with the network
 * information stored in nodes and and edges
 *
 * @param nodes: list of {id: str, label: str, group: {'artifact', 'job'}}
 *  The node information. Id is the unique id of the node (artifact or job),
 *  label is the name to show under the node and group is the type of node
 * @param edges: list of {from: str, to: str, arrows: 'to'}
 *  The connectivity information in the graph. from and to are the nodes of
 *  origin and destination of the edge, respectivelly.
 * @param target: str. The id of the target div to draw the graph
 * @param artifactFunc: function. The function to execute when the user
 *  clicks on a node of group 'artifact'. It should accept only 1 parameter
 *  which is the artifact (node) id
 * @param jobFunc: function. The function to execute when the user clicks on
 *  a node of group 'job'. It should accept only 1 parameter which is the
 *  job (node) id
 *
 */
function draw_processing_graph(nodes, edges, target, artifactFunc, jobFunc) {
  var container = document.getElementById(target);
  container.innerHTML = "";

  var nodes = new vis.DataSet(nodes);
  var edges = new vis.DataSet(edges);
  var data = {
    nodes: nodes,
    edges: edges
  };
  var options = {
    nodes: {
      shape: 'dot',
      font: {
        size: 16,
        color: '#000000'
      },
      size: 13,
      borderWidth: 2,
    },
    edges: {
      color: 'grey'
    },
    layout: {
      hierarchical: {
        direction: "LR",
        sortMethod: "directed",
        levelSeparation: 260
      }
    },
    interaction: {
      dragNodes: false,
      dragView: true,
      zoomView: true,
      selectConnectedEdges: true,
      navigationButtons: true,
      keyboard: true
    },
    groups: {
      jobs: {
        color: '#FF9152'
      },
      artifact: {
        color: '#FFFFFF'
      }
    }
  };

  var network = new vis.Network(container, data, options);
  network.on("click", function (properties) {
    var ids = properties.nodes;
    if (ids.length == 0) {
      return
    }
    // [0] cause only users can only select 1 node
    var clickedNode = nodes.get(ids)[0];
    var element_id = ids[0];
    if (clickedNode.group == 'artifact') {
      artifactFunc(element_id);
    } else {
      jobFunc(element_id);
    }
  });
};

/**
 *
 * Function to show the loading gif in a given div
 *
 * @param portal_dir: string. The portal that qiita is running under
 * @param target: string. The id of the div to populate with the loading gif
 *
 * This function replaces the content of the given div with the
 * gif to show that the section of page is loading
 *
 */
function show_loading(portal_dir, target) {
  $("#" + target).html("<img src='" + portal_dir + "/static/img/waiting.gif' style='display:block;margin-left: auto;margin-right: auto'/>");
}

/**
 *
 * Function to update the name of an artifact
 *
 * @param portal_dir: string. The portal that qiita is running under
 * @param artifact_id: int. The artifact to be changed
 * @param new_name: string. The new artifact name
 * @param on_success_func: function. Function to execute when the name has been
 *        successfully updated
 *
 */
function change_artifact_name(portal_dir, artifact_id, new_name, on_success_func) {
  $.ajax({
    url: portal_dir + '/artifact/' + artifact_id + '/',
    type: 'PATCH',
    data: {'op': 'replace', 'path': '/name/', 'value': new_name},
    success: on_success_func,
    error: function(object, status, error_msg) {
      // Something went wrong, show the message
      bootstrapAlert("Error changing artifact name: " + error_msg, "danger");
    }
  });
}
