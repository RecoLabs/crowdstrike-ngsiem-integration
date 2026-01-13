# reco

### Configure and activate the Reco data connector 

1. In the Falcon console, go to Data connectors > Data connectors > Data connections 
2. Click + Add connection. 
3. In the Data Connectors page, filter or sort by Connector name, Vendor, Product, Connector Type, Author, or Subscription to find and select the connector you want to configure. 
4. In the New connection dialog, review connector metadata, version, and description. Click Configure.
5. In the Add new connector page, enter a name and optional description to identify the connector. 
6. Click the Terms and Conditions box, then click Save. 
7. A banner message appears in the Falcon console when your API key and API URL are ready to be generated. To generate the API key, go to Data connectors > Data connectors > Data connections, click Open menu for the data connector, and click Generate API key. 
8. Copy and safely store the API key and API URL to use during connector configuration.

### Configure the reco connector

1. Modify the config.yaml with reco’s tenant_url (Example: [test.preprod.eu.reco.ai](http://test.preprod.eu.reco.ai/)) & api_key
2. Configure posture & alerts with fetch_limit and cron to provide frequency (Default given cron is 5 minutes)
3. Configure sink. Use API URL as ngsiemurl and API key as token generated during data connector configuration.

**For Linux:**

Execute: `./setup.sh` to install the dependencies and schedule the data connector

***To Uninstall:***

remove the scheduled task by executing: `./uninstall.sh`

And then delete the reco directory

**For Windows:**

Execute: `setup.bat` to install the dependencies and schedule the data connector

***To Uninstall:***

remove the scheduled task by executing: `uninstall.bat`

And then delete the reco directory
