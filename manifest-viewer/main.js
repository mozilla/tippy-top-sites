class Site extends React.PureComponent {
  render() {
    return (
      <div class="tile">
        <img src={this.props.image_url} title={JSON.stringify(this.props.domains)} />
      </div>
    );
  }
}

class Sites extends React.PureComponent {
  render() {
    return (
      <div>
        {this.props.sites.map((site, index) => <Site {...site} />)}
      </div>
    );
  }
}


var myRequest = new Request("https://activity-stream-icons.services.mozilla.com/v1/icons.json.br");

fetch(myRequest)
  .then(function(response) { return response.json(); })
  .then(function(data) {
    ReactDOM.render(
      React.createElement(Sites, {sites: data}, null),
      document.getElementById('root')
    );
  });
