const path = require('path');

module.exports = {
  entry: './src/index.ts',
  // Keep the HACS download small. Source is published in the repository.
  devtool: false,
  mode: 'development',
  module: {
    rules: [
      {
        test: /\.ts$/,
        use: 'ts-loader',
        exclude: /node_modules/,
      },
    ],
  },
  resolve: {
    extensions: ['.tsx', '.ts', '.js'],
  },
  output: {
    filename: 'sip_core.js',
    path: path.resolve(__dirname, 'custom_components', 'sip_core', 'www'),
  },
};
