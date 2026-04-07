export const formatNumber = (num: number) => {
  return new Intl.NumberFormat('ko-KR').format(num);
};
