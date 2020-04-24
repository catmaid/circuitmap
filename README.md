# Circuit Map

Circuit Map is a Django application which can act as a drop-in
extension for [CATMAID](https://catmaid.readthedocs.io/en/latest/extensions.html).

Circuit Map provides tooling to integrate remote skeletons derived from automated segmentations
and automatically generated synaptic link data into CATMAID circuit mapping workflows.

An example use of the tool is based on automatically generated synaptic link data by [Buhmann et al. 2019](https://www.biorxiv.org/content/10.1101/2019.12.12.874172v1) for the [FAFB dataset](http://www.temca2data.org/). Synaptic link data can be added to manually reconstructed skeletons or automatically generated skeletons derived from a [whole brain segmentation](https://fafb-ffn1.storage.googleapis.com/landing.html). Up- and downstream skeleton partners derived from this synaptic link data can be imported automatically into the current CATMAID project.


## Integration into CATMAID

1. Install the dependencies with `pip install -r requirements.txt`.

2. Install circuitmap in whichever python environment is running
CATMAID with `pip install -e .`

3. Make sure your CATMAID instance has RabbitMQ and Celery enabled, it's needed
   to fetch synapses asynchronously. The [documentation](https://catmaid.readthedocs.io/en/stable/celery.html)
   has more information about this.

4. Run `python manage.py migrate` (in the CATMAID folder) to create the circuitmap models.

5. Run `python manage.py collectstatic -l`  (in the CATMAID folder) to pick up
circuitmap's static files.

6. The synaptic link data needs to be ingested into the generated
Postgres table `circuitmap_synlinks` from the [SQL database dump](https://github.com/funkelab/synful_fafb).

7. A few additional settings have to be configured to interoperate with segmentation
data and CATMAID import procedure (see `circuitmap/control/settings.py.example`).

## Usage

Once the extension is installed and integrated into CATMAID, a new API and a
new front-end widget is available in your CATMAID instance. All interaction in
the front-end happens through this widget, this is how it can be opened:

1. On the CATMAID front-page, open the image stack you want to work in
   primarily. In the example FAFB v14 project, click on the *FAFB00 V14 XY*
   link.

2. Select the tracing tool in CATMAID by clicking on the neuron like icon
   button in the top toolbar (![Tracing Tool icon](sphinx-doc/source/_static/trace.svg?sanitize=true)).

3. Click the Circuit Map icon in the top toolbar (![Circuit Map icon]()).
   Should it be hidden due to limited screen space, it is also possible to use
   the *Open Widget* dialog by using the first icon button in the top toolbar
   (![Open Widget icon](sphinx-doc/source/_static/newwindow.svg??sanitize=true) or alterantively Ctrl + Space)
   and searching for "Circuit Map". Enter or doubliclick on the result row will
   open a new *Circuit Map widget*.

Circuit Map can operate in two modes: it can fetch a) all synapses for the
currently selected skeleton and b) fetch a segmentation based skeleton for a
given location along with the synapses linked to it. For both modes, existing
synapses are reused if they are available. Additionally, both modes allow to
also fetch the respective partner fragments for each synapse that is available
from the segmentation data. Both modes are described in more detail below.

### Fetching synapses for the active skeleton.

TBA

### Fetching the segmentation fragment at a location plus its synapses

TBA
