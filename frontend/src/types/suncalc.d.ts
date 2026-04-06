declare module "suncalc" {
  export function getTimes(date: Date, latitude: number, longitude: number): {
    dawn: Date;
    dusk: Date;
    [key: string]: Date;
  };
}
