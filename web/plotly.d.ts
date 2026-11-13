declare module "plotly.js-basic-dist-min" {
  const Plotly: {
    react(el: HTMLElement, data: object[], layout: object, config?: object): Promise<unknown>;
    purge(el: HTMLElement): void;
  };
  export default Plotly;
}
